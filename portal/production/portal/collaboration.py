"""Shared comments and agency quotation decisions backed by real Django records."""
import uuid
from decimal import Decimal

from django import forms
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from .events import record
from .maintenance import access, api_access, payload, requests_for
from .models import Audit, JobActivity, JobComment, JobQuotation, MaintenanceRequest, Membership


def request_key(request):
    try:
        return uuid.UUID(request.headers.get('Idempotency-Key', ''))
    except (ValueError, AttributeError):
        raise ValueError('A UUID Idempotency-Key header is required.')


def lock_job(user, pk):
    MaintenanceRequest.objects.select_for_update().get(pk=pk)
    return get_object_or_404(requests_for(user), pk=pk)


def comment_data(comment, user):
    role, name = comment.author_role, comment.author_name
    return {'id': str(comment.pk), 'text': comment.text,
            'actor': 'Sevlink Operations' if role == 'superadmin' and not user.is_superuser else name,
            'at': comment.created_at.isoformat()}


def quote_data(quote):
    return {'id': str(quote.pk), 'title': quote.title, 'scope': quote.scope,
            'amount': str(quote.amount), 'currency': 'ZAR', 'status': quote.status, 'version': quote.version,
            'decision_reason': quote.decision_reason,
            'created_at': quote.created_at.isoformat(),
            'decided_at': quote.decided_at.isoformat() if quote.decided_at else None}


class CommentForm(forms.Form):
    text = forms.CharField(max_length=2500)


class QuoteForm(forms.Form):
    title = forms.CharField(max_length=180)
    scope = forms.CharField(max_length=3000)
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))

    def clean_amount(self):
        return self.cleaned_data['amount'].quantize(Decimal('0.01'))


class DecisionForm(forms.Form):
    status = forms.ChoiceField(choices=[('approved', 'Approved'), ('rejected', 'Rejected')])
    reason = forms.CharField(max_length=1000, required=False)
    version = forms.IntegerField(min_value=1)

    def clean(self):
        data = super().clean()
        if data.get('status') == 'rejected' and not data.get('reason'):
            self.add_error('reason', 'Explain why this quotation is rejected.')
        return data


def read_form(request, fields, form_class):
    data = payload(request, fields)
    if any(isinstance(value, bool) or not isinstance(value, (str, int, float)) or
           (field not in ('amount', 'version') and not isinstance(value, str)) for field, value in data.items()):
        raise ValueError('Invalid field values.')
    form = form_class(data)
    if not form.is_valid():
        raise ValueError(' '.join(f'{field}: {" ".join(errors)}' for field, errors in form.errors.items()))
    return form.cleaned_data


@api_access
@require_POST
def add_comment(request, job_id):
    get_object_or_404(requests_for(request.user), pk=job_id)
    try:
        key = request_key(request)
        data = read_form(request, ('text',), CommentForm)
    except ValueError as error:
        return JsonResponse({'error': str(error)}, status=400)
    with transaction.atomic():
        job = lock_job(request.user, job_id)
        existing = JobComment.objects.filter(idempotency_key=key).first()
        if existing:
            if existing.author_id != request.user.pk or existing.request_id != job.pk or existing.text != data['text']:
                return JsonResponse({'error': 'Idempotency key conflicts with an earlier submission.'}, status=409)
            return JsonResponse(comment_data(existing, request.user))
        from .events import actor_identity
        role, name = actor_identity(request.user)
        comment = JobComment.objects.create(request=job, author=request.user, author_name=name, author_role=role, text=data['text'], idempotency_key=key)
        record(job, request.user, JobActivity.Kind.COMMENT, 'comment:' + str(comment.pk),
               {'comment_id': str(comment.pk), 'text': comment.text})
        Audit.objects.create(agency=job.property.agency, actor=request.user, action='Shared job comment added', object_id=str(comment.pk))
    return JsonResponse(comment_data(comment, request.user), status=201)


@api_access
@require_POST
def create_quote(request, job_id):
    get_object_or_404(requests_for(request.user), pk=job_id)
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Only Sevlink Super Admin can issue quotations.'}, status=403)
    try:
        key = request_key(request)
        data = read_form(request, ('title', 'scope', 'amount'), QuoteForm)
    except ValueError as error:
        return JsonResponse({'error': str(error)}, status=400)
    with transaction.atomic():
        job = lock_job(request.user, job_id)
        existing = JobQuotation.objects.filter(creation_key=key).first()
        if existing:
            if (existing.created_by_id != request.user.pk or existing.request_id != job.pk or
                    (existing.title, existing.scope, existing.amount) != (data['title'], data['scope'], data['amount'])):
                return JsonResponse({'error': 'Idempotency key conflicts with an earlier quotation.'}, status=409)
            return JsonResponse(quote_data(existing))
        if job.status in ('completed', 'cancelled'):
            return JsonResponse({'error': 'Cannot issue a quotation for a closed request.'}, status=400)
        quote = JobQuotation.objects.create(request=job, created_by=request.user, creation_key=key, **data)
        record(job, request.user, JobActivity.Kind.QUOTE_CREATED, 'quote-created:' + str(quote.pk),
               {'quote_id': str(quote.pk), 'title': quote.title, 'amount': str(quote.amount)})
        Audit.objects.create(agency=job.property.agency, actor=request.user, action='Quotation issued', object_id=str(quote.pk))
    return JsonResponse(quote_data(quote), status=201)


@api_access
@require_POST
def decide_quote(request, job_id, quote_id):
    get_object_or_404(requests_for(request.user), pk=job_id)
    if access(request.user)[0] not in (Membership.PM, Membership.ADMIN):
        return JsonResponse({'error': 'Only an authorized property manager or agency administrator can decide.'}, status=403)
    try:
        key = request_key(request)
        data = read_form(request, ('status', 'reason', 'version'), DecisionForm)
        if type(payload(request, ('status', 'reason', 'version')).get('version')) is not int:
            raise ValueError('An integer quotation version is required.')
    except ValueError as error:
        return JsonResponse({'error': str(error)}, status=400)
    with transaction.atomic():
        job = lock_job(request.user, job_id)
        quote = get_object_or_404(JobQuotation.objects.select_for_update(), pk=quote_id, request=job)
        if quote.decision_key == key:
            if quote.decided_by_id != request.user.pk or quote.status != data['status'] or quote.decision_reason != data['reason']:
                return JsonResponse({'error': 'Idempotency key conflicts with an earlier decision.'}, status=409)
            return JsonResponse(quote_data(quote))
        if JobQuotation.objects.filter(decision_key=key).exists():
            return JsonResponse({'error': 'Idempotency key was used for another decision.'}, status=409)
        if quote.status != 'pending' or quote.version != data['version']:
            return JsonResponse({'error': 'Quotation already decided or changed. Refresh before deciding.'}, status=409)
        if job.status in ('completed', 'cancelled'):
            return JsonResponse({'error': 'Cannot decide a quotation for a closed request.'}, status=400)
        quote.status = data['status']
        quote.version += 1
        quote.decision_key = key
        quote.decision_reason = data['reason']
        quote.decided_by = request.user
        quote.decided_at = timezone.now()
        quote.save()
        kind = JobActivity.Kind.QUOTE_APPROVED if quote.status == 'approved' else JobActivity.Kind.QUOTE_REJECTED
        record(job, request.user, kind, 'quote-decision:' + str(quote.pk),
               {'quote_id': str(quote.pk), 'amount': str(quote.amount), 'status': quote.status, 'reason': quote.decision_reason})
        Audit.objects.create(agency=job.property.agency, actor=request.user, action='Quotation ' + quote.status, object_id=str(quote.pk))
    return JsonResponse(quote_data(quote))
