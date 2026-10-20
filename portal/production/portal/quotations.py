"""Versioned agency quotations. Public money and private cost data never share a snapshot."""
import hashlib
import json
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from .maintenance import api_access, payload, requests_for, access
from .models import JobQuotation, QuotationLine, QuotationPrivate, QuotationAction, Membership
from .collaboration import lock_job, request_key
from .events import record

CENT = Decimal('.01')
MAX_MONEY = Decimal('9999999999.99')


def decimal(value, places, minimum=Decimal(0), maximum=MAX_MONEY):
    if isinstance(value, (bool, float)):
        raise ValueError('Use decimal strings for currency and quantities.')
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < minimum or result > maximum or result != result.quantize(Decimal(1).scaleb(-places)):
            raise ValueError('Invalid decimal precision or range.')
        return result
    except (InvalidOperation, TypeError):
        raise ValueError('Invalid decimal value.') from None


def text(value, limit, required=True):
    if not isinstance(value, str) or len(value.strip()) > limit or (required and not value.strip()):
        raise ValueError('Invalid quotation text.')
    return value.strip()


def content(data):
    title = text(data.get('title'), 180)
    scope = text(data.get('scope', ''), 3000, False)
    treatment = data.get('tax_treatment', 'none')
    if treatment not in ('none', 'exclusive', 'inclusive'):
        raise ValueError('Choose none, exclusive or inclusive VAT treatment.')
    rate = Decimal(0)
    if treatment != 'none':
        if not settings.SEVLINK_VAT_RATE:
            raise ValueError('A Sevlink VAT rate must be configured before taxable quotations can be created.')
        rate = decimal(settings.SEVLINK_VAT_RATE, 6, maximum=Decimal(1))
    raw = data.get('lines')
    # Compatibility with the existing single-amount draft form.
    if raw is None and 'amount' in data:
        raw = [dict(description=title, quantity='1', unit='job', unit_price=data['amount'])]
    if not isinstance(raw, list) or not 1 <= len(raw) <= 20:
        raise ValueError('A quotation requires 1–20 lines.')
    lines = []
    for index, item in enumerate(raw, 1):
        if not isinstance(item, dict) or set(item) != {'description', 'quantity', 'unit', 'unit_price'}:
            raise ValueError('Invalid quotation line fields.')
        qty = decimal(item['quantity'], 3, Decimal('.001'), Decimal('999999999.999'))
        price = decimal(item['unit_price'], 2)
        gross = (qty * price).quantize(CENT, rounding=ROUND_HALF_UP)
        net = (gross / (1 + rate)).quantize(CENT, rounding=ROUND_HALF_UP) if treatment == 'inclusive' else gross
        vat = gross - net if treatment == 'inclusive' else (net * rate).quantize(CENT, rounding=ROUND_HALF_UP)
        total = net + vat
        if total > MAX_MONEY:
            raise ValueError('Quotation exceeds the currency limit.')
        lines.append(dict(position=index, description=text(item['description'], 180), quantity=str(qty),
                          unit=text(item['unit'], 20), unit_price=str(price), net=str(net), vat=str(vat), total=str(total)))
    subtotal = sum((Decimal(line['net']) for line in lines), Decimal(0))
    vat_total = sum((Decimal(line['vat']) for line in lines), Decimal(0))
    amount = subtotal + vat_total
    if not 0 < amount <= MAX_MONEY:
        raise ValueError('Quotation total must be positive and within the currency limit.')
    private = data.get('internal', {})
    if not isinstance(private, dict) or set(private) - {'cost_total', 'commission_total', 'notes'}:
        raise ValueError('Invalid private quotation fields.')
    private = dict(cost_total=decimal(private.get('cost_total', '0'), 2),
                   commission_total=decimal(private.get('commission_total', '0'), 2),
                   notes=text(private.get('notes', ''), 3000, False))
    public = dict(title=title, scope=scope, currency='ZAR', tax_treatment=treatment, vat_rate=str(rate),
                  subtotal=str(subtotal), vat_total=str(vat_total), amount=str(amount), lines=lines)
    return public, private


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def quote_data(quote, user=None):
    public = quote.public_snapshot or dict(title=quote.title, scope=quote.scope, currency='ZAR',
        tax_treatment=quote.tax_treatment, vat_rate=str(quote.vat_rate), subtotal=str(quote.subtotal),
        vat_total=str(quote.vat_total), amount=str(quote.amount), lines=[{
            key: str(getattr(line, key)) if key in ('quantity', 'unit_price', 'net', 'vat', 'total') else getattr(line, key)
            for key in ('position', 'description', 'quantity', 'unit', 'unit_price', 'net', 'vat', 'total')}
            for line in quote.lines.all()])
    result = dict(public, id=str(quote.pk), status=quote.status, version=quote.version,
                  revision=quote.revision, series_id=str(quote.series_id), decision_reason=quote.decision_reason,
                  created_at=quote.created_at.isoformat(), sent_at=quote.sent_at.isoformat() if quote.sent_at else None,
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


def store_content(quote, public, private):
    for field in ('title', 'scope', 'tax_treatment', 'vat_rate', 'subtotal', 'vat_total', 'amount'):
        setattr(quote, field, public[field])
    quote.save()
    quote.lines.all().delete()  # Only called for locked drafts.
    QuotationLine.objects.bulk_create([QuotationLine(quote=quote, **line) for line in public['lines']])
    QuotationPrivate.objects.update_or_create(quote=quote, defaults=private)


def action(quote, user, kind, key, fingerprint, reason=''):
    snapshot = quote.public_snapshot or {k: v for k, v in quote_data(quote).items()
        if k in ('title', 'scope', 'currency', 'tax_treatment', 'vat_rate', 'subtotal', 'vat_total', 'amount', 'lines')}
    QuotationAction.objects.create(quote=quote, actor=user, kind=kind, key=key,
        fingerprint=fingerprint, reason=reason, snapshot=snapshot)
    event_kind = {'created': 'quote_created', 'edited': 'quote_edited', 'sent': 'quote_sent',
                  'revised': 'quote_revised', 'superseded': 'quote_superseded',
                  'approved': 'quote_approved', 'rejected': 'quote_rejected',
                  'revision_requested': 'quote_revision_requested'}[kind]
    details = {'quote_id': str(quote.pk), 'amount': str(quote.amount), 'status': quote.status, 'reason': reason}
    if kind == 'created':
        details = {'quote_id': str(quote.pk), 'title': quote.title, 'amount': str(quote.amount)}
    record(quote.request, user, event_kind, 'quotation-action:' + str(key), details)


@api_access
@require_POST
def create(request, job_id):
    get_object_or_404(requests_for(request.user), pk=job_id)
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Only Sevlink Operations can create drafts.'}, status=403)
    try:
        key = request_key(request)
        data = payload(request, ('title', 'scope', 'amount', 'lines', 'tax_treatment', 'internal'))
        public, private = content(data)
        fingerprint = digest(data)
    except ValueError as error:
        return JsonResponse({'error': str(error)}, status=400)
    with transaction.atomic():
        job = lock_job(request.user, job_id)
        existing = JobQuotation.objects.filter(creation_key=key).first()
        if existing:
            if existing.request_id != job.pk or existing.created_by_id != request.user.pk or existing.creation_fingerprint != fingerprint:
                return JsonResponse({'error': 'Idempotency key conflict.'}, status=409)
            return JsonResponse(quote_data(existing, request.user))
        if QuotationAction.objects.filter(key=key).exists():
            return JsonResponse({'error': 'Idempotency key conflict.'}, status=409)
        if job.status in ('completed', 'cancelled'):
            return JsonResponse({'error': 'The request is closed.'}, status=400)
        quote = JobQuotation(request=job, created_by=request.user, creation_key=key, creation_fingerprint=fingerprint,
                             title=public['title'], scope=public['scope'], amount=public['amount'])
        store_content(quote, public, private)
        action(quote, request.user, 'created', key, fingerprint)
    return JsonResponse(quote_data(quote, request.user), status=201)


@api_access
@require_POST
def mutate(request, job_id, quote_id, operation):
    get_object_or_404(requests_for(request.user), pk=job_id)
    decision = operation == 'decision'
    if (decision and access(request.user)[0] not in (Membership.PM, Membership.ADMIN)) or (not decision and not request.user.is_superuser):
        return JsonResponse({'error': 'You cannot perform this quotation action.'}, status=403)
    try:
        key = request_key(request)
        allowed = ('version', 'status', 'reason') if decision else ('version', 'title', 'scope', 'amount', 'lines', 'tax_treatment', 'internal') if operation == 'edit' else ('version',)
        data = payload(request, allowed)
        if type(data.get('version')) is not int or data['version'] < 1:
            raise ValueError('An integer quotation version is required.')
        reason = ''
        if decision:
            if data.get('status') not in ('approved', 'rejected', 'revision_requested'):
                raise ValueError('Invalid decision.')
            reason = text(data.get('reason'), 1000)
        values = content(data) if operation == 'edit' else None
        fingerprint = digest(dict(data, operation=operation, quote_id=str(quote_id)))
    except ValueError as error:
        return JsonResponse({'error': str(error)}, status=400)
    with transaction.atomic():
        job = lock_job(request.user, job_id)
        quote = get_object_or_404(JobQuotation.objects.select_for_update(), pk=quote_id, request=job)
        if not request.user.is_superuser and quote.status == 'draft':
            return JsonResponse({'error': 'Quotation not found.'}, status=404)
        prior = QuotationAction.objects.filter(key=key).first()
        if prior:
            if prior.actor_id != request.user.pk or prior.fingerprint != fingerprint:
                return JsonResponse({'error': 'Idempotency key conflict.'}, status=409)
            # Revision replay returns the new revision, not its predecessor.
            return JsonResponse(quote_data(prior.quote, request.user))
        if quote.version != data['version'] or job.status in ('completed', 'cancelled'):
            return JsonResponse({'error': 'The quotation or job changed. Refresh before continuing.'}, status=409)
        if decision:
            if quote.status != 'sent':
                return JsonResponse({'error': 'Only the current sent revision can be decided.'}, status=409)
            quote.status = data['status']
            quote.decided_by = request.user
            quote.decided_at = timezone.now()
            quote.decision_key = key
            quote.decision_reason = reason
            kind = quote.status
        elif operation in ('edit', 'send'):
            if quote.status != 'draft':
                return JsonResponse({'error': 'Only drafts can be edited or sent.'}, status=409)
            if operation == 'edit':
                store_content(quote, *values)
                kind = 'edited'
            else:
                quote.public_snapshot = {k: v for k, v in quote_data(quote).items()
                    if k in ('title', 'scope', 'currency', 'tax_treatment', 'vat_rate', 'subtotal', 'vat_total', 'amount', 'lines')}
                quote.status = 'sent'
                quote.sent_at = timezone.now()
                kind = 'sent'
        elif operation == 'revise':
            if quote.status not in ('sent', 'rejected', 'revision_requested'):
                return JsonResponse({'error': 'This revision cannot be superseded. Approved quotations are immutable.'}, status=409)
            quote.status = 'superseded'
            quote.version += 1
            quote.save()
            action(quote, request.user, 'superseded', uuid.uuid4(), fingerprint)
            old = quote
            public = quote_data(old)
            private = QuotationPrivate.objects.filter(quote=old).first()
            quote = JobQuotation(request=job, created_by=request.user, creation_key=uuid.uuid4(),
                series_id=old.series_id, revision=old.revision + 1, previous=old,
                title=old.title, scope=old.scope, amount=old.amount)
            # Preserve the former revision's VAT snapshot until Operations explicitly edits the draft.
            store_content(quote, public, dict(cost_total=private.cost_total, commission_total=private.commission_total,
                notes=private.notes) if private else {})
            action(quote, request.user, 'revised', key, fingerprint)
            return JsonResponse(quote_data(quote, request.user), status=201)
        else:
            return JsonResponse({'error': 'Unknown quotation action.'}, status=404)
        quote.version += 1
        quote.save()
        action(quote, request.user, kind, key, fingerprint, reason)
    return JsonResponse(quote_data(quote, request.user))


@api_access
def pdf(request, job_id, quote_id):
    """Raster PDF from the public snapshot only; no private records are consulted."""
    from io import BytesIO
    import textwrap
    from PIL import Image, ImageDraw, ImageFont
    from django.http import HttpResponse
    if request.method != 'GET':
        return JsonResponse({'error': 'GET required.'}, status=405)
    job = get_object_or_404(requests_for(request.user), pk=job_id)
    if access(request.user)[0] == Membership.TENANT:
        return JsonResponse({'error': 'Quotation access is restricted.'}, status=403)
    qs = JobQuotation.objects.filter(request=job)
    if not request.user.is_superuser:
        qs = qs.exclude(status='draft')
    quote = get_object_or_404(qs, pk=quote_id)
    data = quote_data(quote)
    rows = ['SEVLINK | PROPERTY MAINTENANCE', 'QUOTATION — ZAR',
        f'Job: SV-{str(job.pk).upper()}', f'Agency: {job.property.agency.name}',
        f'Property: {job.property.name}', f'Revision: {quote.revision} | Status: {quote.get_status_display()}',
        data['title'], data['scope'], '']
    for line in data['lines']:
        rows.extend([line['description'], f"{line['quantity']} {line['unit']} x ZAR {line['unit_price']} | VAT {line['vat']} | Total {line['total']}", ''])
    rows += [f"VAT treatment: {data['tax_treatment']} | Rate: {data['vat_rate']}",
             f"Subtotal: ZAR {data['subtotal']}", f"VAT: ZAR {data['vat_total']}", f"TOTAL: ZAR {data['amount']}"]
    wrapped = [part for row in rows for part in (textwrap.wrap(row, 90) or [''])]
    pages = []
    font = ImageFont.load_default(size=17)
    for start in range(0, len(wrapped), 48):
        page = Image.new('RGB', (1240, 1754), 'white')
        draw = ImageDraw.Draw(page)
        draw.rectangle((0, 0, 1240, 18), fill='#f58220')
        for index, row in enumerate(wrapped[start:start+48]):
            draw.text((65, 65 + index*32), row, fill='#102b46', font=font)
        pages.append(page)
    output = BytesIO()
    pages[0].save(output, format='PDF', save_all=True, append_images=pages[1:], resolution=150)
    response = HttpResponse(output.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Sevlink-quotation-{quote.pk}-r{quote.revision}.pdf"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
