"""Committed account outbox, leased delivery outside transactions, sanitized attempts."""
import uuid
from datetime import timedelta
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMessage, get_connection
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone
from .models import MailQueue, AccountMailAttempt, OperationsWorkerHeartbeat


def deliver(limit=50, preview=False):
    if not preview:
        if connection.in_atomic_block:
            raise ImproperlyConfigured('Live delivery must run outside a database transaction.')
        if (not settings.SMTP_DELIVERY_ENABLED or not settings.EMAIL_HOST or
                not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD or
                settings.EMAIL_USE_TLS == settings.EMAIL_USE_SSL):
            raise ImproperlyConfigured('SMTP delivery disabled or secure configuration incomplete.')
    delivered=0
    for _ in range(limit):
        now=timezone.now()
        OperationsWorkerHeartbeat.objects.update_or_create(name='accounts',defaults={'at':now})
        with transaction.atomic():
            rows=MailQueue.objects.filter(sent_at=None,retired_at=None).filter(
                Q(attempts__lt=5,next_attempt_at__lte=now)|Q(expires_at__lte=now)).filter(
                Q(lease_token=None)|Q(lease_expires_at__lt=now)).order_by('pk')
            rows=rows.select_for_update(skip_locked=True) if connection.features.has_select_for_update_skip_locked else rows.select_for_update()
            item=rows.first()
            if not item:
                break
            if item.expires_at and item.expires_at<=now:
                item.retired_at=now;item.error_code='expired';item.body='[Expired account link removed]'
                item.lease_token=None;item.lease_expires_at=None
                item.save()
                AccountMailAttempt.objects.create(message=item,number=item.attempts,outcome='expired')
                continue
            token=uuid.uuid4()
            item.lease_token=token;item.lease_expires_at=now+timedelta(minutes=5)
            item.attempts+=1;item.save()
        # Preview never consumes the live queue or marks delivery successful.
        outcome='error'
        try:
            backend='portal.mail.PrivatePreviewBackend' if preview else 'django.core.mail.backends.smtp.EmailBackend'
            provider=get_connection(backend)
            message=EmailMessage(item.subject,item.body,to=[item.recipient],connection=provider,
                                 headers={'Message-ID':f'<sevlink-account-{item.pk}@sevlink.co.za>'})
            if message.send(fail_silently=False)!=1:
                raise OSError('Provider did not accept message.')
            outcome='preview' if preview else 'accepted'
        except Exception:
            outcome='error'
        with transaction.atomic():
            saved=MailQueue.objects.select_for_update().get(pk=item.pk)
            if saved.lease_token!=token:
                continue
            AccountMailAttempt.objects.create(message=saved,number=saved.attempts,outcome=outcome)
            saved.lease_token=None;saved.lease_expires_at=None
            if outcome=='accepted':
                saved.sent_at=timezone.now();saved.body='[Delivered; account link removed]';saved.error_code=''
                delivered+=1
            elif outcome=='preview':
                saved.attempts-=1
                saved.next_attempt_at=timezone.now()+timedelta(minutes=5)
                saved.error_code='preview_only'
            else:
                saved.error_code='delivery_failed'
                saved.next_attempt_at=timezone.now()+timedelta(seconds=min(3600,30*2**saved.attempts))
            saved.save()
        if preview:
            break
    return delivered
