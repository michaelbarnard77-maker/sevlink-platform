"""Private per-operator inbox, independent of email delivery and business state."""
import uuid
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from .maintenance import api_access, payload
from .models import OperationsInboxItem, OperationsInboxReceipt
from .events import record


def items(user):
    read = OperationsInboxReceipt.objects.filter(item=OuterRef('pk'), user=user, read_at__isnull=False)
    return OperationsInboxItem.objects.select_related('event').annotate(read=Exists(read))


@api_access
@require_GET
def feed(request):
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Sevlink Operations access required.'}, status=403)
    try:
        before = int(request.GET['before']) if 'before' in request.GET else None
    except ValueError:
        return JsonResponse({'error': 'Invalid page cursor.'}, status=400)
    qs = items(request.user)
    unread = qs.filter(read=False).count()
    if before:
        cursor = get_object_or_404(OperationsInboxItem, pk=before)
        qs = qs.filter(Q(created_at__lt=cursor.created_at) | Q(created_at=cursor.created_at, pk__lt=cursor.pk))
    page = list(qs.order_by('-created_at', '-pk')[:51])
    return JsonResponse({'unread_count': unread, 'next': page[49].pk if len(page) > 50 else None,
        'items': [{'id': item.pk, 'read': item.read, 'type': item.event.kind,
            'event': item.event.get_kind_display(), 'agency': item.event.agency_name,
            'property': item.event.property_name, 'job_number': item.event.request.reference,
            'job_id': str(item.event.request_id), 'at': item.event.created_at.isoformat(),
            'url': reverse('maintenance_workspace') + '?job=' + str(item.event.request_id)} for item in page[:50]]})


@api_access
@require_POST
def state(request, item_id):
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Sevlink Operations access required.'}, status=403)
    try:
        data = payload(request, ('read',))
        if set(data) != {'read'} or type(data['read']) is not bool:
            raise ValueError('A boolean read state is required.')
    except ValueError as error:
        return JsonResponse({'error': str(error)}, status=400)
    with transaction.atomic():
        item = get_object_or_404(OperationsInboxItem.objects.select_for_update().select_related('event__request__property__agency'), pk=item_id)
        receipt, _ = OperationsInboxReceipt.objects.get_or_create(item=item, user=request.user)
        if bool(receipt.read_at) != data['read']:
            receipt.read_at = timezone.now() if data['read'] else None
            receipt.save(update_fields=['read_at'])
            record(item.event.request, request.user, 'notification_state', 'notification-state:' + str(uuid.uuid4()),
                   {'notification_id': str(item.pk), 'read': str(data['read']).lower()})
    return JsonResponse({'id': item_id, 'read': data['read']})


@api_access
@require_POST
def conversation_permissions(request, job_id):
    from .collaboration import lock_job
    from .maintenance import requests_for
    get_object_or_404(requests_for(request.user), pk=job_id)
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Only Sevlink Operations can change conversation permissions.'}, status=403)
    try:
        data = payload(request, ('version', 'tenant_comments_allowed'))
        if type(data.get('version')) is not int or type(data.get('tenant_comments_allowed')) is not bool:
            raise ValueError('An integer version and boolean permission are required.')
    except ValueError as error:
        return JsonResponse({'error': str(error)}, status=400)
    with transaction.atomic():
        job = lock_job(request.user, job_id)
        if job.version != data['version']:
            return JsonResponse({'error': 'Job changed. Refresh before continuing.'}, status=409)
        if job.tenant_comments_allowed != data['tenant_comments_allowed']:
            job.tenant_comments_allowed = data['tenant_comments_allowed']
            job.version += 1
            job.save(update_fields=['tenant_comments_allowed', 'version', 'updated_at'])
            record(job, request.user, 'conversation_permission', 'conversation-permission:' + str(uuid.uuid4()),
                   {'tenant_comments_allowed': str(job.tenant_comments_allowed).lower()})
    return JsonResponse({'tenant_comments_allowed': job.tenant_comments_allowed, 'version': job.version})
