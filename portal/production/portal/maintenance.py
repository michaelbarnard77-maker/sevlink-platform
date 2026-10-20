"""Authenticated maintenance API. Never serialize a model's __dict__ or internal fields."""
import json
import hashlib
import uuid
import re
from functools import wraps

from django import forms
from django.conf import settings
from django.db import transaction, IntegrityError
from django.db.models import F
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods
from django.contrib.auth.decorators import login_required

from .models import Audit, Membership, Property, MaintenanceRequest, MaintenanceStatusEvent

CATEGORIES = (
    'Plumbing', 'Electrical', 'Doors & locks', 'Painting', 'Tiling',
    'General maintenance', 'Roofing', 'Gutters & Downpipes', 'Damp & Waterproofing',
    'Ceilings & Drywall', 'Carpentry & Cupboards', 'Windows & Glass',
    'Gates & Garage Doors', 'Appliances', 'Air Conditioning & Ventilation',
    'Gardens & Outdoor Areas', 'Pest Control', 'Cleaning & Waste Removal',
    'Renovations & Refurbishments',
)
S = MaintenanceRequest.Status
TRANSITIONS = {
    S.AWAITING_REVIEW: (S.REVIEWED, S.CANCELLED),
    S.REVIEWED: (S.IN_PROGRESS, S.CANCELLED),
    S.IN_PROGRESS: (S.COMPLETED, S.CANCELLED),
    S.COMPLETED: (), S.CANCELLED: (),
}


def access(user):
    # Cross-agency access is explicit: ordinary is_staff users do not qualify.
    if user.is_active and user.is_superuser:
        return 'superadmin', None
    membership = Membership.objects.filter(user=user).first()
    if user.is_active and membership and membership.role in (Membership.ADMIN, Membership.PM, Membership.TENANT):
        return membership.role, membership
    return None, None


def properties_for(user):
    role, membership = access(user)
    if role == 'superadmin':
        return Property.objects.all()
    if not membership:
        return Property.objects.none()
    qs = Property.objects.filter(agency=membership.agency)
    if role == Membership.ADMIN:
        return qs
    if role == Membership.PM:
        return qs.filter(manager=user)
    return qs.filter(tenancy__user=user, tenancy__active=True).distinct()


def requests_for(user):
    role, _ = access(user)
    qs = MaintenanceRequest.objects.filter(property__in=properties_for(user))
    if role == Membership.TENANT:
        qs = qs.filter(reported_by=user)
    return qs.select_related('property__agency', 'property__manager').prefetch_related('status_events', 'attachments', 'activities', 'comments', 'quotations')


def api_access(view):
    @wraps(view)
    @never_cache
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_active:
            return JsonResponse({'error': 'Authentication required.'}, status=401)
        if not access(request.user)[0]:
            return JsonResponse({'error': 'No maintenance workspace access.'}, status=403)
        return view(request, *args, **kwargs)
    return wrapped


def payload(request, allowed):
    if request.content_type != 'application/json':
        raise ValueError('Send application/json.')
    if len(request.body) > 16384:
        raise ValueError('Request is too large.')
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        raise ValueError('Invalid JSON.')
    if not isinstance(data, dict) or set(data) - set(allowed):
        raise ValueError('Unexpected request fields.')
    return data


def property_data(prop):
    return {'id': str(prop.pk), 'name': prop.name, 'address': prop.address,
            'agency': prop.agency.name,
            'manager': (prop.manager.get_full_name() or 'Property manager') if prop.manager else 'Agency administrator'}


def serialize(job, user):
    from .attachments import attachment_data
    from .events import activity_data
    from .collaboration import comment_data
    from .quotations import quote_data
    from .attachments import visible_attachments
    role, _ = access(user)
    can_update = role in ('superadmin', Membership.ADMIN, Membership.PM)
    return {
        'id': str(job.pk), 'reference': 'SV-' + str(job.pk).upper(),
        'property': property_data(job.property), 'title': job.title,
        'description': job.description, 'category': job.category,
        'status': job.status, 'status_label': job.get_status_display(),
        'attachments': [attachment_data(a) for a in visible_attachments(job, user)],
        'tenant_comments_allowed': job.tenant_comments_allowed,
        'comments': [comment_data(c, user) for c in job.comments.all() if (user.is_superuser or c.visibility == 'shared') and (role != Membership.TENANT or job.tenant_comments_allowed)],
        'quotations': [quote_data(q, user) for q in job.quotations.all() if user.is_superuser or q.status != 'draft'] if role != Membership.TENANT else [],
        'activity': [activity_data(e, user) for e in job.activities.all()
                     if (user.is_superuser or e.visibility == 'shared') and (role != Membership.TENANT or (not e.kind.startswith('quote_') and (job.tenant_comments_allowed or e.kind != 'comment_added')))],
        'version': job.version, 'created_at': job.created_at.isoformat(),
        'updated_at': job.updated_at.isoformat(),
        'allowed_statuses': [{'value': s, 'label': S(s).label} for s in TRANSITIONS[job.status]] if can_update else [],
        'history': [{'status': event.status, 'label': S(event.status).label, 'at': event.at.isoformat()}
                    for event in job.status_events.all()],
    }


class ReportForm(forms.Form):
    property = forms.ModelChoiceField(queryset=Property.objects.none())
    title = forms.CharField(max_length=180)
    description = forms.CharField(max_length=2500)
    category = forms.ChoiceField(choices=[(c, c) for c in CATEGORIES])

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['property'].queryset = properties_for(user)


@api_access
@require_GET
@ensure_csrf_cookie
def context(request):
    role, _ = access(request.user)
    return JsonResponse({
        'user': {'name': request.user.get_full_name() or request.user.username, 'role': role},
        'can_report': role == Membership.TENANT,
        'properties': [property_data(p) for p in properties_for(request.user).select_related('agency', 'manager')],
        'categories': list(CATEGORIES),
    })


@api_access
@require_http_methods(['GET', 'POST'])
def collection(request):
    if request.method == 'GET':
        try:
            page = int(request.GET.get('page', '1'))
            if page < 1 or page > 1000000:
                raise ValueError
        except ValueError:
            return JsonResponse({'error': 'Invalid page.'}, status=400)
        qs = requests_for(request.user)
        count = qs.count()
        jobs = qs[(page - 1) * 50:page * 50]
        return JsonResponse({'results': [serialize(j, request.user) for j in jobs], 'count': count,
                             'next': page + 1 if page * 50 < count else None})
    if access(request.user)[0] != Membership.TENANT:
        return JsonResponse({'error': 'Only linked tenants can submit reports.'}, status=403)
    from . import attachments
    keys = []
    submission_key = None
    fingerprint = ''
    try:
        if request.headers.get('Idempotency-Key'):
            try:
                submission_key = uuid.UUID(request.headers['Idempotency-Key'])
            except ValueError:
                raise ValueError('Idempotency-Key must be a UUID.')
        if request.content_type == 'multipart/form-data':
            data, uploads = attachments.multipart(request, ('property', 'title', 'description', 'category'))
        else:
            data = payload(request, ('property', 'title', 'description', 'category'))
            uploads = []
        if any(not isinstance(value, str) for value in data.values()):
            raise ValueError('Report fields must be text.')
        form = ReportForm(data, user=request.user)
        if not form.is_valid():
            return JsonResponse({'error': 'Please check the report fields.', 'fields': form.errors.get_json_data()}, status=400)
        prepared = attachments.prepare(uploads)
        fingerprint = hashlib.sha256(json.dumps({
            'fields': {key: str(value.pk) if key == 'property' else value for key, value in form.cleaned_data.items()},
            'attachments': [(item['filename'], hashlib.sha256(item['data']).hexdigest()) for item in prepared],
        }, sort_keys=True).encode()).hexdigest()
        with transaction.atomic():
            if submission_key:
                existing = MaintenanceRequest.objects.filter(submission_key=submission_key).first()
                if existing:
                    if existing.reported_by_id != request.user.pk or existing.submission_fingerprint != fingerprint:
                        return JsonResponse({'error': 'Idempotency key conflicts with an earlier report.'}, status=409)
                    return JsonResponse(serialize(get_object_or_404(requests_for(request.user), pk=existing.pk), request.user))
            job = MaintenanceRequest.objects.create(reported_by=request.user, submission_key=submission_key,
                                                     submission_fingerprint=fingerprint, **form.cleaned_data)
            MaintenanceStatusEvent.objects.create(request=job, actor=request.user, status=job.status)
            Audit.objects.create(agency=job.property.agency, actor=request.user,
                                 action='Maintenance request submitted', object_id=str(job.pk))
            attachments.save_files(job, request.user, prepared, keys)
            from .events import record
            record(job, request.user, 'job_submitted', 'submitted:' + str(job.pk), {'status': job.status})
    except IntegrityError:
        attachments.cleanup(keys)
        existing = MaintenanceRequest.objects.filter(submission_key=submission_key).first() if submission_key else None
        if existing and existing.reported_by_id == request.user.pk and existing.submission_fingerprint == fingerprint:
            return JsonResponse(serialize(get_object_or_404(requests_for(request.user), pk=existing.pk), request.user))
        raise
    except ValueError as error:
        attachments.cleanup(keys)
        return JsonResponse({'error': str(error)}, status=400)
    except attachments.UploadStorageError:
        attachments.cleanup(keys)
        return JsonResponse({'error': 'Attachment storage is unavailable. Report was not saved.'}, status=503)
    except Exception:
        attachments.cleanup(keys)
        raise
    return JsonResponse(serialize(requests_for(request.user).get(pk=job.pk), request.user), status=201)


@api_access
@require_http_methods(['GET', 'PATCH'])
def detail(request, job_id):
    job = get_object_or_404(requests_for(request.user), pk=job_id)
    if request.method == 'GET':
        return JsonResponse(serialize(job, request.user))
    if access(request.user)[0] not in ('superadmin', Membership.ADMIN, Membership.PM):
        return JsonResponse({'error': 'Only an authorized manager can update status.'}, status=403)
    try:
        data = payload(request, ('status', 'version'))
        if set(data) != {'status', 'version'} or type(data['version']) is not int or not isinstance(data['status'], str):
            raise ValueError('Status and integer version are required.')
    except ValueError as error:
        return JsonResponse({'error': str(error)}, status=400)
    if data['version'] != job.version:
        return JsonResponse({'error': 'This request changed. Refresh before updating.'}, status=409)
    if data['status'] not in TRANSITIONS[job.status]:
        return JsonResponse({'error': 'Invalid status transition.'}, status=400)
    with transaction.atomic():
        updated = MaintenanceRequest.objects.filter(
            pk=job.pk, version=data['version'], property__in=properties_for(request.user)
        ).update(
            status=data['status'], version=F('version') + 1, updated_at=timezone.now())
        if not updated:
            return JsonResponse({'error': 'This request changed. Refresh before updating.'}, status=409)
        MaintenanceStatusEvent.objects.create(request=job, actor=request.user, status=data['status'])
        from .events import record
        kind = {'cancelled': 'job_cancelled', 'completed': 'job_completed'}.get(data['status'], 'status_changed')
        record(job, request.user, kind, f'status:{job.pk}:{job.version + 1}', {'status': data['status']})
        Audit.objects.create(agency=job.property.agency, actor=request.user,
                             action='Maintenance status: ' + data['status'], object_id=str(job.pk))
    return JsonResponse(serialize(requests_for(request.user).get(pk=job.pk), request.user))


@login_required
@never_cache
@ensure_csrf_cookie
@require_GET
def workspace(request):
    if not access(request.user)[0]:
        return HttpResponse('No maintenance workspace access.', status=403)
    # Reuse the existing portal shell and all its CSS, without running demo scripts
    # or embedding demo identities/private browser data in the authenticated UI.
    html = (settings.PORTAL_UI_DIR / 'index.html').read_text()
    from django.templatetags.static import static
    html = html.replace('<head>', '<head><base href="' + static('maintenance-ui/') + '">', 1)
    html = re.sub(r'<script\b[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    html = html.replace('</body>', '<script src="' + static('maintenance.js') + '"></script></body>')
    # Avoid exposing the sample identity/demo labels in the first server response.
    html = re.sub(r'<div class="profile">.*?</header>', '<div class="profile"></div></header>', html, flags=re.DOTALL)
    html = re.sub(r'<nav id="nav">.*?</nav>', '<nav id="nav"></nav>', html, flags=re.DOTALL)
    html = re.sub(r'<footer>.*?</footer>', '<footer>Sevlink · Property maintenance</footer>', html, flags=re.DOTALL)
    return HttpResponse(html)
