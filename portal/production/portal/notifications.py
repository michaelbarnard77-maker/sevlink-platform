"""Leased outbox delivery. No network calls run inside job transactions."""
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMultiAlternatives, get_connection
from django.utils.html import escape
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from .events import notification_message
from .models import OperationsNotification, OperationsDeliveryAttempt

MAX_ATTEMPTS = 5
LEASE_SECONDS = 300
LOCAL_BACKENDS = {'portal.mail.PrivatePreviewBackend', 'django.core.mail.backends.filebased.EmailBackend', 'django.core.mail.backends.locmem.EmailBackend'}


def claim():
    now = timezone.now()
    with transaction.atomic():
        while True:
            due = Q(state='pending', next_attempt_at__lte=now) | Q(state='sending', lease_expires_at__lte=now)
            query = OperationsNotification.objects.filter(due).order_by('created_at', 'pk')
            if connection.features.has_select_for_update_skip_locked:
                query = query.select_for_update(skip_locked=True)
            else:
                query = query.select_for_update()
            notification = query.first()
            if not notification:
                return None
            if notification.state == 'sending':
                OperationsDeliveryAttempt.objects.filter(notification=notification, number=notification.attempts,
                    outcome='sending').update(outcome='uncertain', finished_at=now, error_code='lease_expired')
            if notification.attempts >= MAX_ATTEMPTS:
                notification.state = 'dead'
                notification.error_code = 'retry_exhausted'
                notification.lease_token = notification.lease_expires_at = None
                notification.save()
                continue
            notification.state = 'sending'
            notification.attempts += 1
            notification.lease_token = uuid.uuid4()
            notification.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
            notification.save()
            OperationsDeliveryAttempt.objects.create(notification=notification, number=notification.attempts)
            return notification


def deliver(limit=50):
    backend = settings.OPERATIONS_EMAIL_DELIVERY_BACKEND
    if backend not in LOCAL_BACKENDS and not settings.OPERATIONS_LIVE_DELIVERY_ENABLED:
        raise ImproperlyConfigured('Operations live delivery is disabled. Use a local testing backend.')
    if backend == 'portal.mail.QueueBackend':
        raise ImproperlyConfigured('Operations delivery cannot enqueue itself into the account mail queue.')
    processed = 0
    for _ in range(limit):
        notification = claim()
        if notification is None:
            break
        error = ''
        try:
            event = notification.event
            subject, body = notification_message(event)
            message = EmailMultiAlternatives(subject, body, settings.DEFAULT_FROM_EMAIL, [notification.recipient],
                connection=get_connection(backend),
                headers={'Message-ID': f'<sevlink-event-{event.pk}@notifications.sevlink.co.za>'})
            message.attach_alternative('<html><body style="font-family:Arial;color:#102b46">'
                '<div style="border-top:6px solid #f58220;padding:24px"><h1>SEVLINK</h1>'
                '<p>PROPERTY MAINTENANCE · OPERATIONS</p><h2>' + escape(event.get_kind_display()) + '</h2>'
                '<pre style="white-space:pre-wrap;font-family:Arial">' + escape(body) + '</pre>'
                '<p>Confidential Operations notification. Sign in to review the saved job.</p></div></body></html>', 'text/html')
            if message.send(fail_silently=False) != 1:
                raise RuntimeError('Delivery backend did not accept the message.')
        except Exception:
            # Never persist provider errors: they can contain credentials or message content.
            error = 'delivery_failed'
        now = timezone.now()
        with transaction.atomic():
            current = OperationsNotification.objects.select_for_update().get(pk=notification.pk)
            if current.state != 'sending' or current.lease_token != notification.lease_token:
                # A reclaimed worker owns the record; do not overwrite its result.
                processed += 1
                continue
            current.lease_token = current.lease_expires_at = None
            current.error_code = error
            if error:
                current.state = 'dead' if current.attempts >= MAX_ATTEMPTS else 'pending'
                current.next_attempt_at = now + timedelta(seconds=min(3600, 60 * 2 ** (current.attempts - 1)))
            else:
                current.state = 'sent'
                current.sent_at = now
            current.save()
            OperationsDeliveryAttempt.objects.filter(notification=current, number=current.attempts,
                outcome='sending').update(outcome='failed' if error else 'sent', finished_at=now, error_code=error)
        processed += 1
    return processed
