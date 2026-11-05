"""Trusted provider feedback ingestion and audited dead-letter replay. No public webhook."""
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .models import OperationsNotification, OperationsFeedback, OperationsReplay, OperationsFeedbackResolution


def feedback(data):
    """Normalized event from a signature-verified provider adapter or trusted operator."""
    import uuid
    try:
        if not isinstance(data,dict) or set(data)!={'event_id','provider_event_id','kind','occurred_at'}:
            raise ValueError()
        event_id=uuid.UUID(str(data['event_id']))
        kind=data['kind']
        key=data['provider_event_id']
        at=parse_datetime(data['occurred_at'])
        if kind not in ('delivered','bounce','complaint') or not isinstance(key,str) or not 1<=len(key)<=180 or not at or timezone.is_naive(at) or at>timezone.now()+timedelta(minutes=5):
            raise ValueError()
    except (ValueError,TypeError,AttributeError):
        raise ValueError('Invalid normalized, verified email feedback.') from None
    with transaction.atomic():
        notification=OperationsNotification.objects.select_for_update().get(event_id=event_id)
        existing=OperationsFeedback.objects.filter(provider_event_id=key).first()
        if existing:
            if existing.notification_id != notification.pk or existing.kind!=kind or existing.occurred_at!=at:
                raise ValueError('Provider feedback key conflicts with an existing event.')
            return False
        OperationsFeedback.objects.create(notification=notification,provider_event_id=key,kind=kind,occurred_at=at)
        update_feedback_status(notification)
        if kind in ('bounce','complaint') and notification.state in ('pending','sending'):
            notification.state='dead'
            notification.error_code='recipient_suppressed'
            notification.lease_token=notification.lease_expires_at=None
        notification.save()
    return True


def replay(notification_id, actor, reason):
    if not actor.is_active or not actor.is_superuser or not isinstance(reason,str) or not 1<=len(reason.strip())<=1000:
        raise ValueError('Active Operations user and a replay reason are required.')
    with transaction.atomic():
        item=OperationsNotification.objects.select_for_update().get(pk=notification_id)
        if item.state!='dead' or item.feedback_status=='delivered' or OperationsFeedback.objects.filter(
                notification__recipient=item.recipient,kind__in=['bounce','complaint'],resolution__isnull=True).exists():
            raise ValueError('Only failed, unsuppressed, unconfirmed-delivery messages can be replayed.')
        OperationsReplay.objects.create(notification=item,actor=actor,reason=reason.strip())
        item.retry_limit=item.attempts+5
        item.state='pending';item.error_code='';item.next_attempt_at=timezone.now()
        item.lease_token=item.lease_expires_at=None
        item.save()


def update_feedback_status(notification):
    unresolved=notification.feedback.filter(resolution__isnull=True)
    notification.feedback_status=('complaint' if unresolved.filter(kind='complaint').exists() else
        'bounce' if unresolved.filter(kind='bounce').exists() else
        'delivered' if notification.feedback.filter(kind='delivered').exists() else 'unknown')


def resolve_feedback(feedback_id,actor,reason):
    if not actor.is_active or not actor.is_superuser or not isinstance(reason,str) or not 1<=len(reason.strip())<=1000:
        raise ValueError('Active Operations user and resolution reason required.')
    with transaction.atomic():
        event=OperationsFeedback.objects.get(pk=feedback_id)
        notification=OperationsNotification.objects.select_for_update().get(pk=event.notification_id)
        if event.kind not in ('bounce','complaint'):
            raise ValueError('Only negative feedback needs a deliverability resolution.')
        resolution,created=OperationsFeedbackResolution.objects.get_or_create(feedback=event,defaults={'actor':actor,'reason':reason.strip()})
        if not created:
            return False
        update_feedback_status(notification)
        notification.save(update_fields=['feedback_status'])
    return True
