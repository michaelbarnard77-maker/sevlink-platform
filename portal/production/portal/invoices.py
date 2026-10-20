"""Manually uploaded invoices and an append-only manual payment ledger. No gateway."""
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
from .models import JobInvoice, InvoicePayment, Membership
from .quotations import digest


def invoice_data(invoice, user):
    payments = []
    for payment in invoice.payments.all():
        row = {'amount': str(payment.amount), 'paid_on': payment.paid_on.isoformat(),
               'at': payment.created_at.isoformat()}
        if user.is_superuser:
            row.update(reference=payment.reference, note=payment.note, actor=payment.actor.get_full_name() or 'Sevlink Operations')
        payments.append(row)
    result = {'id': str(invoice.pk), 'number': invoice.number, 'amount': str(invoice.amount), 'currency':'ZAR',
        'due_date': invoice.due_date.isoformat(), 'uploaded_at': invoice.created_at.isoformat(),
        'paid_amount': str(invoice.paid_amount), 'outstanding': str(invoice.amount-invoice.paid_amount),
        'payment_status': invoice.payment_status, 'version': invoice.version, 'payments': payments,
        'document': document_data(invoice.document, reverse('maintenance_invoice_pdf',args=[invoice.request_id,invoice.pk]))}
    if user.is_superuser:
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
        data,prepared=uploaded_pdf(request,('number','amount','due_date','visibility'))
        values=dict(number=text(data.get('number'),80), amount=money(data.get('amount')),
                    due_date=day(data.get('due_date')), visibility=data.get('visibility','internal'))
        if values['visibility'] not in ('shared','internal'):
            raise ValueError('Choose agency-visible or Operations-only invoice visibility.')
        fingerprint=digest(dict(values,file=file_fingerprint(prepared)))
        with transaction.atomic():
            job=lock_job(request.user,job_id)
            existing=JobInvoice.objects.filter(creation_key=key).first()
            if existing:
                if existing.request_id != job.pk or existing.uploaded_by_id != request.user.pk or existing.fingerprint != fingerprint:
                    return JsonResponse({'error':'Idempotency key conflict.'},status=409)
                return JsonResponse(invoice_data(existing,request.user))
            if JobInvoice.objects.filter(request=job,visibility=values['visibility'],number__iexact=values['number']).exists():
                return JsonResponse({'error':'This invoice number already exists for this job and visibility.'},status=409)
            document=attachments.save_files(job,request.user,prepared,keys,visibility='internal',purpose='invoice')[0]
            invoice=JobInvoice.objects.create(request=job,document=document,uploaded_by=request.user,
                creation_key=key,fingerprint=fingerprint,**values)
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


@api_access
@require_POST
def pay(request,job_id,invoice_id):
    get_object_or_404(requests_for(request.user),pk=job_id)
    if not request.user.is_superuser:
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
        job=lock_job(request.user,job_id)
        invoice=get_object_or_404(JobInvoice.objects.select_for_update(),pk=invoice_id,request=job)
        prior=InvoicePayment.objects.filter(key=key).first()
        if prior:
            if prior.invoice_id != invoice.pk or prior.actor_id != request.user.pk or prior.fingerprint != fingerprint:
                return JsonResponse({'error':'Idempotency key conflict.'},status=409)
            return JsonResponse(invoice_data(invoice,request.user))
        if invoice.version != data['version']:
            return JsonResponse({'error':'Invoice changed. Refresh before recording payment.'},status=409)
        total=invoice.paid_amount+values['amount']
        if total > invoice.amount:
            return JsonResponse({'error':'Payment exceeds the recorded outstanding amount.'},status=400)
        InvoicePayment.objects.create(invoice=invoice,actor=request.user,key=key,fingerprint=fingerprint,**values)
        invoice.paid_amount=total
        invoice.payment_status='paid' if total == invoice.amount else 'partially_paid'
        invoice.version+=1
        invoice.save(update_fields=['paid_amount','payment_status','version'])
        audit(invoice,request.user,'invoice_payment',key,values['amount'])
    return JsonResponse(invoice_data(invoice,request.user),status=201)


@api_access
@require_GET
def pdf(request,job_id,invoice_id):
    job=get_object_or_404(requests_for(request.user),pk=job_id)
    if access(request.user)[0] == Membership.TENANT:
        return JsonResponse({'error':'Invoice access is restricted.'},status=403)
    qs=JobInvoice.objects.filter(request=job).select_related('document')
    if not request.user.is_superuser:
        qs=qs.filter(visibility='shared')
    invoice=get_object_or_404(qs,pk=invoice_id)
    return attachments.file_response(invoice.document)
