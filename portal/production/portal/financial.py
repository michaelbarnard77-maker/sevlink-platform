"""Manual adjustments: never initiate transfers or rewrite issued files/payment rows."""
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from . import attachments
from .commercial import money, text, day, uploaded_pdf, file_fingerprint
from .collaboration import lock_job, request_key
from .events import record
from .maintenance import api_access, requests_for, payload, access
from .models import JobInvoice, InvoicePayment, InvoiceRefund, InvoiceAction, InvoiceCreditNote, Membership
from .numbering import allocate
from .quotations import digest


def net_paid(invoice):
    return invoice.paid_amount - invoice.refunded_amount


def set_payment_state(invoice):
    net = net_paid(invoice)
    invoice.payment_status = ('unpaid' if not invoice.paid_amount else 'refunded') if net == 0 else ('paid' if net == invoice.amount else 'partially_paid')


def ledger_action(invoice, actor, kind, key, fingerprint, reason='', reference=''):
    InvoiceAction.objects.create(invoice=invoice, actor=actor, kind=kind, key=key,
        fingerprint=fingerprint, reason=reason, reference=reference, snapshot={
            'gross_paid':str(invoice.paid_amount), 'refunded':str(invoice.refunded_amount),
            'net_paid':str(net_paid(invoice)), 'payment_status':invoice.payment_status,
            'document_status':invoice.document_status, 'reconciliation_required':invoice.reconciliation_required})
    record(invoice.request, actor, kind, 'invoice-adjustment:'+str(key),
        {'invoice_id':str(invoice.pk), 'number':invoice.number, 'amount':str(invoice.amount), 'status':invoice.document_status},
        private=invoice.visibility == 'internal')


@api_access
@require_POST
def adjust(request, job_id, invoice_id, operation):
    from .invoices import invoice_data
    get_object_or_404(requests_for(request.user),pk=job_id)
    if not request.user.is_superuser:
        return JsonResponse({'error':'Only Sevlink Operations can record financial adjustments.'},status=403)
    keys=[]
    try:
        key=request_key(request)
        prepared=None
        if operation in ('correct','credit-notes'):
            fields=('version','number','amount','due_date','reason') if operation == 'correct' else ('version','reference','amount','issued_on','reason')
            data,prepared=uploaded_pdf(request,fields)
            if not data.get('version','').isdigit():
                raise ValueError('An integer invoice version is required.')
            data['version']=int(data['version'])
        else:
            fields={'refunds':('version','payment_id','amount','refunded_on','reason','reference','confirmation'),
                    'void':('version','reason','voided_on','accounting_reference','accounting_reviewed','confirmation'),
                    'reconcile':('version','reason','reference','confirmation')} .get(operation)
            if not fields:
                return JsonResponse({'error':'Unknown adjustment.'},status=404)
            data=payload(request,fields)
        if type(data.get('version')) is not int or data['version'] < 1:
            raise ValueError('An integer invoice version is required.')
        reason=text(data.get('reason'),1000)
        reference=text(data.get('reference',''),180,False)
        if operation == 'refunds':
            if data.get('confirmation') != 'REFUND':
                raise ValueError('Additional REFUND confirmation is required. This only records a manual refund.')
            values=dict(amount=money(data.get('amount')),refunded_on=day(data.get('refunded_on')),
                        reference=text(data.get('reference'),180),reason=reason)
            if values['refunded_on'] > timezone.localdate():
                raise ValueError('A recorded refund cannot be dated in the future.')
            try:
                if isinstance(data.get('payment_id'), (bool,float)):
                    raise ValueError('Invalid payment ID.')
                payment_id=int(data.get('payment_id'))
            except (ValueError,TypeError):
                raise ValueError('A valid original payment is required.') from None
        elif operation == 'void':
            if data.get('confirmation') != 'VOID' or data.get('accounting_reviewed') is not True:
                raise ValueError('VOID confirmation and external accounting review acknowledgement are required.')
            voided_on=day(data.get('voided_on'))
            if voided_on > timezone.localdate():
                raise ValueError('Void date cannot be in the future.')
            reference=text(data.get('accounting_reference'),180)
        elif operation == 'reconcile':
            if data.get('confirmation') != 'RECONCILE':
                raise ValueError('Additional RECONCILE confirmation is required.')
            reference=text(data.get('reference'),180)
        elif operation == 'correct':
            values=dict(number=text(data.get('number'),80),amount=money(data.get('amount')),due_date=day(data.get('due_date')))
        else:
            values=dict(reference=text(data.get('reference'),80),amount=money(data.get('amount')),
                        issued_on=day(data.get('issued_on')),reason=reason)
            if values['issued_on'] > timezone.localdate():
                raise ValueError('Credit note issue date cannot be in the future.')
        fingerprint=digest(dict(data,operation=operation,invoice_id=str(invoice_id),file=file_fingerprint(prepared) if prepared else None))
        with transaction.atomic():
            job=lock_job(request.user,job_id)
            invoice=get_object_or_404(JobInvoice.objects.select_for_update(),pk=invoice_id,request=job)
            prior=InvoiceAction.objects.filter(key=key).first()
            if prior:
                if prior.actor_id != request.user.pk or prior.fingerprint != fingerprint:
                    return JsonResponse({'error':'Idempotency key conflict.'},status=409)
                return JsonResponse(invoice_data(prior.invoice,request.user))
            if InvoicePayment.objects.filter(key=key).exists() or JobInvoice.objects.filter(creation_key=key).exists():
                return JsonResponse({'error':'Idempotency key conflict.'},status=409)
            if invoice.version != data['version']:
                return JsonResponse({'error':'Invoice changed. Refresh before continuing.'},status=409)
            if operation == 'refunds':
                payment=get_object_or_404(InvoicePayment.objects.select_for_update(),pk=payment_id,invoice=invoice)
                refunded=payment.refunds.aggregate(total=Sum('amount'))['total'] or Decimal(0)
                if values['amount'] > payment.amount-refunded:
                    return JsonResponse({'error':'Refund exceeds the unrefunded original payment amount.'},status=400)
                if values['refunded_on'] < payment.paid_on:
                    raise ValueError('Refund date cannot precede its payment date.')
                InvoiceRefund.objects.create(invoice=invoice,payment=payment,actor=request.user,key=key,**values)
                invoice.refunded_amount+=values['amount']
                set_payment_state(invoice)
                kind='invoice_refund'
            elif operation == 'void':
                if invoice.document_status != 'active':
                    return JsonResponse({'error':'Invoice is already void.'},status=409)
                invoice.document_status='void'
                invoice.void_reason=reason
                invoice.voided_on=voided_on
                invoice.voided_at=timezone.now()
                invoice.voided_by=request.user
                invoice.accounting_reference=reference
                invoice.reconciliation_required=invoice.paid_amount > 0
                kind='invoice_void'
            elif operation == 'correct':
                if invoice.document_status != 'void' or JobInvoice.objects.filter(previous=invoice).exists():
                    return JsonResponse({'error':'Only a void invoice without a replacement can be corrected.'},status=409)
                matches=JobInvoice.objects.filter(subcontractor_id=invoice.subcontractor_id,number__iexact=values['number'])
                if invoice.subcontractor_id is None: matches=matches.filter(request=job,visibility=invoice.visibility)
                if matches.exists():
                    return JsonResponse({'error':'Replacement must use a distinct externally issued invoice number.'},status=409)
                document=attachments.save_files(job,request.user,prepared,keys,visibility='internal',purpose='invoice')[0]
                old=invoice
                invoice=JobInvoice.objects.create(request=job,document=document,uploaded_by=request.user,
                    record_number=allocate('SI'),previous=old,correction_reason=reason,subcontractor_id=old.subcontractor_id,
                    visibility=old.visibility,reconciliation_required=old.reconciliation_required or net_paid(old)>0,
                    creation_key=key,fingerprint=fingerprint,**values)
                invoice.refresh_from_db()
                ledger_action(invoice,request.user,'invoice_corrected',key,fingerprint,reason)
                return JsonResponse(invoice_data(invoice,request.user),status=201)
            elif operation == 'reconcile':
                if not invoice.reconciliation_required:
                    return JsonResponse({'error':'Invoice has no reconciliation hold.'},status=409)
                if (invoice.document_status == 'void' and net_paid(invoice) != 0) or (invoice.previous_id and
                        (invoice.previous.reconciliation_required or net_paid(invoice.previous) != 0)):
                    return JsonResponse({'error':'Original funds must first be refunded and the original hold reconciled. No automatic allocation occurs.'},status=409)
                invoice.reconciliation_required=False
                kind='invoice_reconciled'
            else:
                if invoice.credit_notes.filter(reference__iexact=values['reference']).exists():
                    return JsonResponse({'error':'Credit note reference already recorded.'},status=409)
                document=attachments.save_files(job,request.user,prepared,keys,visibility='internal',purpose='credit_note')[0]
                InvoiceCreditNote.objects.create(invoice=invoice,document=document,actor=request.user,**values)
                kind='invoice_credit_note'
            invoice.version+=1
            invoice.save()
            ledger_action(invoice,request.user,kind,key,fingerprint,reason,reference)
    except ValueError as error:
        attachments.cleanup(keys)
        return JsonResponse({'error':str(error)},status=400)
    except attachments.UploadStorageError:
        attachments.cleanup(keys)
        return JsonResponse({'error':'Private document storage is unavailable.'},status=503)
    except Exception:
        attachments.cleanup(keys)
        raise
    return JsonResponse(invoice_data(invoice,request.user),status=201)


@api_access
@require_GET
def credit_pdf(request,job_id,invoice_id,note_id):
    job=get_object_or_404(requests_for(request.user),pk=job_id)
    if access(request.user)[0] == Membership.TENANT:
        return JsonResponse({'error':'Commercial document access is restricted.'},status=403)
    qs=JobInvoice.objects.filter(request=job)
    if not request.user.is_superuser:
        qs=qs.filter(visibility='shared')
    invoice=get_object_or_404(qs,pk=invoice_id)
    note=get_object_or_404(InvoiceCreditNote.objects.select_related('document'),pk=note_id,invoice=invoice)
    return attachments.file_response(note.document)
