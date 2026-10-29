"""Uploaded quotation PDF revisions, metadata and agency decisions; no calculations/generation."""
import hashlib
import json
import uuid
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.http import require_POST, require_GET

from .maintenance import api_access, payload, requests_for, access
from .models import JobQuotation, QuotationPrivate, QuotationAction, QuoteApprovalReplacement, Membership
from .collaboration import lock_job, request_key
from .events import record
from .numbering import reserve_quote_reference, approve_job_number
from . import attachments
from .commercial import money, text, uploaded_pdf, file_fingerprint, document_data


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def quote_data(quote, user=None):
    # Explicit allowlist: historical calculation/supplier fields never enter the new API.
    public = dict(title=quote.title, scope=quote.scope, reference=quote.reference,
                  currency='ZAR', amount=str(quote.amount),
                  document=document_data(quote.document, reverse('maintenance_quote_pdf', args=[quote.request_id, quote.pk])) if quote.document_id else None,
                  legacy_without_pdf=not bool(quote.document_id))
    replaced=QuoteApprovalReplacement.objects.filter(original=quote).first()
    result = dict(public, record_number=quote.record_number, amends_id=str(quote.amends_id) if quote.amends_id else None,
                  amendment_reason=quote.amendment_reason, amends_record_number=quote.amends.record_number if quote.amends_id else None, amends_reference=quote.amends.reference if quote.amends_id else None,
                  has_next_revision=JobQuotation.objects.filter(previous=quote).exists(), approval_valid=quote.status == 'approved' and not replaced,
                  superseded_by_approval=str(replaced.replacement_id) if replaced else None, id=str(quote.pk), status=quote.status, version=quote.version,
                  revision=quote.revision, series_id=str(quote.series_id), decision_reason=quote.decision_reason,
                  decision_actor=(quote.decided_by.get_full_name() or 'Agency decision') if quote.decided_by_id and (user and user.is_superuser or not quote.decided_by.is_superuser) else 'Sevlink Operations' if quote.decided_by_id else None, created_at=quote.created_at.isoformat(), sent_at=quote.sent_at.isoformat() if quote.sent_at else None,
                  decided_at=quote.decided_at.isoformat() if quote.decided_at else None,
                  history=[{'action': a.kind, 'reason': a.reason, 'at': a.created_at.isoformat(),
                            'actor': a.actor.get_full_name() if user and user.is_superuser else
                            ('Agency decision' if a.kind in ('approved', 'rejected', 'revision_requested') else 'Sevlink Operations')}
                           for a in quote.actions.select_related('actor').all()
                           if (user and user.is_superuser) or a.kind in ('sent', 'approved', 'rejected', 'revision_requested', 'superseded')])
    if user and user.is_superuser:
        private = QuotationPrivate.objects.filter(quote=quote).first()
        result['internal'] = dict(cost_total=str(private.cost_total), commission_total=str(private.commission_total), notes=private.notes) if private else {}
    return result


def action(quote, user, kind, key, fingerprint, reason=''):
    snapshot = quote.public_snapshot or {k: v for k, v in quote_data(quote).items()
        if k in ('record_number','amends_id','amendment_reason','title', 'scope', 'reference', 'currency', 'amount', 'document')}
    QuotationAction.objects.create(quote=quote, actor=user, kind=kind, key=key,
        fingerprint=fingerprint, reason=reason, snapshot=snapshot)
    event_kind = {'amended':'quote_amended', 'effective':'quote_amendment_active', 'created': 'quote_created', 'edited': 'quote_edited', 'sent': 'quote_sent',
                  'revised': 'quote_revised', 'superseded': 'quote_superseded',
                  'approved': 'quote_approved', 'rejected': 'quote_rejected',
                  'revision_requested': 'quote_revision_requested'}[kind]
    details = {'quote_id': str(quote.pk), 'amount': str(quote.amount), 'status': quote.status, 'reason': reason}
    if kind == 'created':
        details = {'quote_id': str(quote.pk), 'title': quote.title, 'amount': str(quote.amount)}
    record(quote.request, user, event_kind, 'quotation-action:' + str(key), details)


def upload_fields(data):
    reference = text(data.get('reference'), 80)
    return dict(reference=reference, title=text(data.get('title', reference), 180),
                scope=text(data.get('scope', ''), 3000, False), amount=money(data.get('amount')))


@api_access
@require_POST
def create(request, job_id):
    return create_uploaded(request,job_id,publish=False)


@api_access
@require_POST
def upload(request,job_id):
    return create_uploaded(request,job_id,publish=True)


def create_uploaded(request,job_id,publish=False):
    get_object_or_404(requests_for(request.user), pk=job_id)
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Only Sevlink Operations can upload quotation PDFs.'}, status=403)
    keys = []
    try:
        key = request_key(request)
        data, prepared = uploaded_pdf(request, ('reference', 'title', 'scope', 'amount'))
        values = upload_fields(data)
        fingerprint = digest(dict(values, file=file_fingerprint(prepared), **({"publish":True} if publish else {})))
        with transaction.atomic():
            job = lock_job(request.user, job_id)
            existing = JobQuotation.objects.filter(creation_key=key).first()
            if existing:
                if existing.request_id != job.pk or existing.created_by_id != request.user.pk or existing.creation_fingerprint != fingerprint:
                    return JsonResponse({'error': 'Idempotency key conflict.'}, status=409)
                return JsonResponse(quote_data(existing, request.user))
            if QuotationAction.objects.filter(key=key).exists():
                return JsonResponse({'error': 'Idempotency key conflict.'}, status=409)
            if job.workflow_version and job.job_type!='quoted':
                raise ValueError('The PM must classify this request as Quotation Required. Additional quoted call-out work needs its own linked request.')
            if publish:
                from .workflow import effective_quotes
                if job.quotations.filter(status__in=('draft','sent','revision_requested')).exists() or effective_quotes(job).exists():
                    return JsonResponse({'error':'A current quote already exists. Use the PM-requested revision or approved amendment workflow.'},status=409)
            if job.status in ('completed', 'cancelled', 'closed'):
                return JsonResponse({'error': 'The request is closed.'}, status=400)
            series_id = uuid.uuid4()
            reserve_quote_reference(values['reference'], series_id)
            document = attachments.save_files(job, request.user, prepared, keys,
                visibility='internal', purpose='quotation')[0]
            quote = JobQuotation.objects.create(request=job, created_by=request.user, document=document,
                series_id=series_id, creation_key=key, creation_fingerprint=fingerprint, **values)
            action(quote, request.user, 'created', key, fingerprint)
            if publish:
                quote.public_snapshot = {k:v for k,v in quote_data(quote).items()
                    if k in ('record_number','amends_id','amendment_reason','title','scope','reference','currency','amount','document')}
                quote.status='sent'
                quote.sent_at=timezone.now()
                quote.version+=1
                quote.save()
                action(quote,request.user,'sent',uuid.uuid5(key,'upload-and-send'),fingerprint)

    except ValueError as error:
        attachments.cleanup(keys)
        return JsonResponse({'error': str(error)}, status=400)
    except attachments.UploadStorageError:
        attachments.cleanup(keys)
        return JsonResponse({'error': 'Private document storage is unavailable.'}, status=503)
    except Exception:
        attachments.cleanup(keys)
        raise
    return JsonResponse(quote_data(quote, request.user), status=201)


@api_access
@require_POST
def mutate(request, job_id, quote_id, operation):
    get_object_or_404(requests_for(request.user), pk=job_id)
    publish_revision=operation=='revise-and-send'
    if publish_revision:operation='revise'
    decision = operation == 'decision'
    if (decision and access(request.user)[0] not in (Membership.PM, Membership.ADMIN)) or (not decision and not request.user.is_superuser):
        return JsonResponse({'error': 'You cannot perform this quotation action.'}, status=403)
    keys = []
    try:
        key = request_key(request)
        prepared = None
        if operation in ('revise','amend'):
            data, prepared = uploaded_pdf(request, ('version','reference','title','scope','amount','reason'))
            if not data.get('version', '').isdigit():
                raise ValueError('An integer quotation version is required.')
            data['version'] = int(data['version'])
            values = upload_fields(data)
        else:
            allowed = ('version', 'status', 'reason') if decision else ('version','reference','title','scope','amount') if operation == 'edit' else ('version',)
            data = payload(request, allowed)
            values = upload_fields(data) if operation == 'edit' else None
        if type(data.get('version')) is not int or data['version'] < 1:
            raise ValueError('An integer quotation version is required.')
        reason = text(data.get('reason'),1000) if operation == 'amend' else ''
        if decision:
            if data.get('status') not in ('approved', 'rejected', 'revision_requested'):
                raise ValueError('Invalid decision.')
            reason = text(data.get('reason'), 1000)
        fingerprint = digest(dict(data, operation=operation, quote_id=str(quote_id),
                                  file=file_fingerprint(prepared) if prepared else None,**({'publish':True} if publish_revision else {})))
        with transaction.atomic():
            job = lock_job(request.user, job_id)
            quote = get_object_or_404(JobQuotation.objects.select_for_update(), pk=quote_id, request=job)
            if job.workflow_version and job.job_type!='quoted':
                return JsonResponse({'error':'Quoted work must use a separately classified quotation-required request.'},status=409)
            if not request.user.is_superuser and quote.status == 'draft':
                return JsonResponse({'error': 'Quotation not found.'}, status=404)
            prior = QuotationAction.objects.filter(key=key).first()
            if prior:
                if prior.actor_id != request.user.pk or prior.fingerprint != fingerprint:
                    return JsonResponse({'error': 'Idempotency key conflict.'}, status=409)
                return JsonResponse(quote_data(prior.quote, request.user))
            if JobQuotation.objects.filter(creation_key=key).exists():
                return JsonResponse({'error': 'Idempotency key conflict.'}, status=409)
            if quote.version != data['version'] or job.status in ('completed', 'cancelled', 'closed'):
                return JsonResponse({'error': 'The quotation or job changed. Refresh before continuing.'}, status=409)
            if decision:
                if quote.status != 'sent' or not quote.document_id:
                    return JsonResponse({'error': 'Only a current sent quotation with an uploaded PDF can be decided.'}, status=409)
                if quote.amends_id and QuoteApprovalReplacement.objects.filter(original_id=quote.amends_id).exists():
                    return JsonResponse({'error':'The original approval has already been replaced. Refresh.'},status=409)
                quote.status = data['status']
                quote.decided_by = request.user
                quote.decided_at = timezone.now()
                quote.decision_key = key
                quote.decision_reason = reason
                kind = quote.status
            elif operation in ('edit', 'send'):
                if quote.status != 'draft' or not quote.document_id:
                    return JsonResponse({'error': 'Only uploaded PDF drafts can be edited or sent.'}, status=409)
                if operation == 'edit':
                    reserve_quote_reference(values['reference'], quote.series_id)
                    for field, value in values.items():
                        setattr(quote, field, value)
                    kind = 'edited'
                else:
                    reserve_quote_reference(quote.reference, quote.series_id)
                    quote.public_snapshot = {k: v for k, v in quote_data(quote).items()
                        if k in ('record_number','amends_id','amendment_reason','title','scope','reference','currency','amount','document')}
                    quote.status = 'sent'
                    quote.sent_at = timezone.now()
                    kind = 'sent'
            elif operation in ('revise','amend'):
                if operation == 'amend':
                    if quote.status != 'approved' or QuoteApprovalReplacement.objects.filter(original=quote).exists() or JobQuotation.objects.filter(previous=quote).exists():
                        return JsonResponse({'error':'Only the current approved quotation without an amendment can be amended. Use the existing amendment revision chain.'},status=409)
                elif quote.status not in ('sent','rejected','revision_requested'):
                    return JsonResponse({'error': 'This revision cannot be superseded. Approved quotations are immutable.'}, status=409)
                if operation=='revise' and not quote.amends_id and quote.status!='revision_requested':
                    return JsonResponse({'error':'The PM must request a revision before a replacement quote can be uploaded.'},status=409)
                reserve_quote_reference(values['reference'], quote.series_id)
                document = attachments.save_files(job, request.user, prepared, keys,
                    visibility='internal', purpose='quotation')[0]
                if operation == 'revise':
                    quote.status = 'superseded'
                    quote.version += 1
                    quote.save()
                    action(quote, request.user, 'superseded', uuid.uuid4(), fingerprint)
                old = quote
                quote = JobQuotation.objects.create(request=job, created_by=request.user, document=document,
                    amends=old if operation == 'amend' else old.amends,
                    amendment_reason=reason if operation == 'amend' else old.amendment_reason,
                    creation_key=uuid.uuid4(), creation_fingerprint=fingerprint, series_id=old.series_id,
                    revision=old.revision+1, previous=old, **values)
                action(quote, request.user, 'amended' if operation == 'amend' else 'revised', key, fingerprint, reason)
                if publish_revision:
                    quote.public_snapshot={k:v for k,v in quote_data(quote).items() if k in ('record_number','amends_id','amendment_reason','title','scope','reference','currency','amount','document')}
                    quote.status='sent';quote.sent_at=timezone.now();quote.version+=1;quote.save()
                    action(quote,request.user,'sent',uuid.uuid5(key,'revision-upload-and-send'),fingerprint)
                return JsonResponse(quote_data(quote, request.user), status=201)
            else:
                return JsonResponse({'error': 'Unknown quotation action.'}, status=404)
            quote.version += 1
            quote.save()
            if decision and quote.status == 'approved':
                approve_job_number(job)
            if decision and quote.status == 'approved' and quote.amends_id:
                QuoteApprovalReplacement.objects.create(original_id=quote.amends_id,replacement=quote,actor=request.user)
                action(quote,request.user,'effective',uuid.uuid4(),fingerprint,'Replacement approval now effective; original PDF/decision retained.')
            action(quote, request.user, kind, key, fingerprint, reason)
    except ValueError as error:
        attachments.cleanup(keys)
        return JsonResponse({'error': str(error)}, status=400)
    except attachments.UploadStorageError:
        attachments.cleanup(keys)
        return JsonResponse({'error': 'Private document storage is unavailable.'}, status=503)
    except Exception:
        attachments.cleanup(keys)
        raise
    return JsonResponse(quote_data(quote, request.user))


@api_access
@require_GET
def pdf(request, job_id, quote_id):
    """Download the original uploaded bytes; never synthesize a PDF."""
    job = get_object_or_404(requests_for(request.user), pk=job_id)
    if access(request.user)[0] == Membership.TENANT:
        return JsonResponse({'error': 'Quotation access is restricted.'}, status=403)
    qs = JobQuotation.objects.filter(request=job)
    if not request.user.is_superuser:
        qs = qs.exclude(status='draft')
    quote = get_object_or_404(qs.select_related('document'), pk=quote_id, document__isnull=False)
    return attachments.file_response(quote.document)
