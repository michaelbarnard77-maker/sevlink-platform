"""Manually uploaded invoices and an append-only manual payment ledger. No gateway."""
import uuid
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from . import attachments
from .commercial import money, text, day, uploaded_pdf, file_fingerprint, document_data
from .collaboration import lock_job, request_key
from .events import record
from .maintenance import api_access, requests_for, payload, access
from .staff_access import can_pay
from .models import MaintenanceRequest, JobInvoice, InvoicePayment, Membership, Subcontractor, JobAssignment
from .quotations import digest
from .financial import net_paid, set_payment_state
from .commercial import MAX_MONEY


def invoice_data(invoice, user):
    internal=user.is_superuser
    payments = []
    for payment in invoice.payments.all():
        row = {'amount': str(payment.amount), 'paid_on': payment.paid_on.isoformat(),
               'at': payment.created_at.isoformat()}
        if internal:
            refunded=sum((r.amount for r in payment.refunds.all()),0)
            row.update(id=payment.pk, refundable=str(payment.amount-refunded), reference=payment.reference, note=payment.note, actor=payment.actor.get_full_name() or 'Sevlink Operations')
        payments.append(row)
    replacement=JobInvoice.objects.filter(previous=invoice).first()
    result = {'replacement_id':str(replacement.pk) if replacement else None, 'record_number':invoice.record_number, 'previous_id':str(invoice.previous_id) if invoice.previous_id else None,
        'document_status':invoice.document_status,'reconciliation_required':invoice.reconciliation_required,
        'refunded_amount':str(invoice.refunded_amount),'net_paid_amount':str(net_paid(invoice)),
        'recorded_balance':str(invoice.amount-net_paid(invoice)),
        'purpose':invoice.purpose, 'id': str(invoice.pk), 'number': invoice.number, 'amount': str(invoice.amount), 'currency':'ZAR',
        'due_date': invoice.due_date.isoformat(), 'uploaded_at': invoice.created_at.isoformat(),
        'paid_amount': str(invoice.paid_amount), 'outstanding': str(invoice.amount-net_paid(invoice) if invoice.document_status == 'active' else invoice.amount*0),
        'payment_status': invoice.payment_status, 'version': invoice.version, 'payments': payments,
        'document': document_data(invoice.document, reverse('maintenance_invoice_pdf',args=[invoice.request_id,invoice.pk]))}
    result['collectible'] = result['outstanding'] if not invoice.reconciliation_required else '0.00'
    result['credit_notes']=[{'id':n.pk,'reference':n.reference,'amount':str(n.amount),'issued_on':n.issued_on.isoformat(),
        'document':document_data(n.document,reverse('maintenance_credit_pdf',args=[invoice.request_id,invoice.pk,n.pk]))} for n in invoice.credit_notes.select_related('document')]
    result['refunds']=[dict(amount=str(r.amount),refunded_on=r.refunded_on.isoformat(),
        **({'payment_id':r.payment_id,'reason':r.reason,'reference':r.reference,'actor':r.actor.get_full_name() or 'Sevlink Operations','at':r.created_at.isoformat()} if internal else {})) for r in invoice.refunds.select_related('actor')]
    if internal:
        result.update(void_reason=invoice.void_reason,voided_on=invoice.voided_on.isoformat() if invoice.voided_on else None,
            accounting_reference=invoice.accounting_reference,correction_reason=invoice.correction_reason,
            voided_by=invoice.voided_by.get_full_name() if invoice.voided_by_id else None,
            financial_history=[dict(type=a.kind,actor=a.actor.get_full_name() or 'Sevlink Operations',at=a.created_at.isoformat(),reason=a.reason,reference=a.reference) for a in invoice.actions.select_related('actor')])
        result['visibility'] = invoice.visibility
    return result


def audit(invoice, actor, kind, key, amount):
    record(invoice.request, actor, kind, 'invoice-action:'+str(key),
           {'invoice_id':str(invoice.pk), 'number':invoice.number, 'amount':str(amount), 'status':invoice.payment_status},
           private=invoice.visibility == 'internal')


@api_access
@require_POST
def create(request, job_id):
    get_object_or_404(requests_for(request.user),pk=job_id)
    if not request.user.is_superuser:
        return JsonResponse({'error':'Only Sevlink Operations can upload invoice PDFs.'},status=403)
    keys=[]
    try:
        key=request_key(request)
        data,prepared=uploaded_pdf(request,('number','amount','due_date','visibility','subcontractor','purpose'))
        values=dict(number=text(data.get('number'),80), amount=money(data.get('amount')),
                    due_date=day(data['due_date']) if data.get('due_date') else timezone.localdate(), visibility=data.get('visibility','internal'))
        if values['visibility'] not in ('shared','internal'):
            raise ValueError('Choose agency-visible or Operations-only invoice visibility.')
        if values['visibility']=='shared' and not data.get('due_date'):raise ValueError('Record the due date printed on the agency invoice.')
        supplier_id=uuid.UUID(data['subcontractor']) if data.get('subcontractor') else None
        if supplier_id and values['visibility']!='internal':
            raise ValueError('Subcontractor invoices are Operations-only.')
        purpose=data.get('purpose','final' if values['visibility']=='shared' else 'supplier')
        if purpose not in ('deposit','final','supplier'):raise ValueError('Choose deposit, final or private supplier invoice.')
        if values['visibility']=='shared' and purpose=='supplier':raise ValueError('Supplier invoices are private.')
        if values['visibility']=='internal':purpose='supplier'
        fingerprint_values=dict(values,purpose=purpose,file=file_fingerprint(prepared))
        if supplier_id: fingerprint_values['subcontractor']=str(supplier_id)
        fingerprint=digest(fingerprint_values)
        with transaction.atomic():
            job=lock_job(request.user,job_id)
            supplier=get_object_or_404(Subcontractor,pk=supplier_id) if supplier_id else None
            if supplier and not JobAssignment.objects.filter(request=job,subcontractor=supplier).exists():
                raise ValueError('Select a job previously assigned to this subcontractor.')
            existing=JobInvoice.objects.filter(creation_key=key).first()
            if existing:
                if existing.request_id != job.pk or existing.uploaded_by_id != request.user.pk or existing.fingerprint != fingerprint:
                    return JsonResponse({'error':'Idempotency key conflict.'},status=409)
                return JsonResponse(invoice_data(existing,request.user))
            matches=JobInvoice.objects.filter(subcontractor=supplier,number__iexact=values['number'])
            if supplier is None: matches=matches.filter(request=job,visibility=values['visibility'])
            if matches.exists():
                return JsonResponse({'error':'This invoice number already exists for this job and visibility.'},status=409)
            if job.workflow_version and values['visibility']=='internal' and not supplier:raise ValueError('Select the subcontractor assigned to this job for a private supplier invoice.')
            if job.workflow_version and values['visibility']=='shared':
                from .workflow import completion_valid,check_ceiling
                if purpose=='final' and (job.status!='completed' or not completion_valid(job)):
                    raise ValueError('Accepted completion report, after photos, before photos or audited exception, and completed work are required before the final invoice.')
                if purpose=='deposit' and job.job_type!='quoted':raise ValueError('Call-outs do not require deposit invoices.')
                check_ceiling(job,values['amount'])
            if supplier:
                from datetime import timedelta
                today=timezone.localdate()
                values['due_date']=today+timedelta(days=(7-today.weekday())%7 or 7)
            document=attachments.save_files(job,request.user,prepared,keys,visibility='internal',purpose='invoice')[0]
            invoice=JobInvoice.objects.create(request=job,document=document,uploaded_by=request.user,subcontractor=supplier,
                purpose=purpose,creation_key=key,fingerprint=fingerprint,**values)
            # Reload typed Decimal/Date values before serializing, including on SQLite.
            invoice.refresh_from_db()
            audit(invoice,request.user,'invoice_uploaded',key,invoice.amount)
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


def payment_job(user,job_id,invoice_id,lock=False):
    if not user.is_superuser and can_pay(user):
        get_object_or_404(JobInvoice,pk=invoice_id,request_id=job_id,visibility='internal',subcontractor__isnull=False)
        qs=MaintenanceRequest.objects.select_for_update() if lock else MaintenanceRequest.objects.all()
        return get_object_or_404(qs,pk=job_id)
    return lock_job(user,job_id) if lock else get_object_or_404(requests_for(user),pk=job_id)


@api_access
@require_POST
def pay(request,job_id,invoice_id):
    payment_job(request.user,job_id,invoice_id)
    if not can_pay(request.user):
        return JsonResponse({'error':'Only Sevlink Operations can record manual payments.'},status=403)
    try:
        key=request_key(request)
        data=payload(request,('version','amount','paid_on','reference','note'))
        if type(data.get('version')) is not int or data['version'] < 1:
            raise ValueError('An integer invoice version is required.')
        values=dict(amount=money(data.get('amount')),paid_on=day(data.get('paid_on')),
                    reference=text(data.get('reference',''),180,False),note=text(data.get('note',''),1000,False))
        if values['paid_on'] > timezone.localdate():
            raise ValueError('A received payment cannot have a future date.')
        fingerprint=digest(dict(data,invoice_id=str(invoice_id)))
    except ValueError as error:
        return JsonResponse({'error':str(error)},status=400)
    with transaction.atomic():
        job=payment_job(request.user,job_id,invoice_id,lock=True)
        invoice=get_object_or_404(JobInvoice.objects.select_for_update(),pk=invoice_id,request=job)
        if invoice.subcontractor_id and not values['reference']:
            return JsonResponse({'error':'Record the external payment reference.'},status=400)
        prior=InvoicePayment.objects.filter(key=key).first()
        if prior:
            if prior.invoice_id != invoice.pk or prior.actor_id != request.user.pk or prior.fingerprint != fingerprint:
                return JsonResponse({'error':'Idempotency key conflict.'},status=409)
            return JsonResponse(invoice_data(invoice,request.user))
        if invoice.version != data['version']:
            return JsonResponse({'error':'Invoice changed. Refresh before recording payment.'},status=409)
        if invoice.document_status != 'active' or invoice.reconciliation_required:
            return JsonResponse({'error':'Invoice is void or on reconciliation hold; no payments may be collected.'},status=409)
        total=invoice.paid_amount+values['amount']
        if total-invoice.refunded_amount > invoice.amount or total > MAX_MONEY:
            return JsonResponse({'error':'Payment exceeds the recorded outstanding amount.'},status=400)
        InvoicePayment.objects.create(invoice=invoice,actor=request.user,key=key,fingerprint=fingerprint,**values)
        invoice.paid_amount=total
        set_payment_state(invoice)
        invoice.version+=1
        invoice.save(update_fields=['paid_amount','payment_status','version'])
        audit(invoice,request.user,'invoice_payment',key,values['amount'])
        from .workflow import after_payment
        after_payment(job,request.user)
    return JsonResponse(invoice_data(invoice,request.user),status=201)


@api_access
@require_GET
def pdf(request,job_id,invoice_id):
    job=payment_job(request.user,job_id,invoice_id)
    if access(request.user)[0] == Membership.TENANT:
        return JsonResponse({'error':'Invoice access is restricted.'},status=403)
    qs=JobInvoice.objects.filter(request=job).select_related('document')
    if not request.user.is_superuser:
        qs=qs.filter(visibility='internal',subcontractor__isnull=False) if can_pay(request.user) else qs.filter(visibility='shared',subcontractor=None)
    invoice=get_object_or_404(qs,pk=invoice_id)
    return attachments.file_response(invoice.document)
