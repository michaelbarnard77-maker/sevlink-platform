import hashlib, secrets
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import Invitation, MailQueue, RateBucket

def digest(raw):
    return hashlib.sha256(raw.encode()).hexdigest()

def limited(key,maximum=10,minutes=15):
    with transaction.atomic():
        key = digest(key)
        RateBucket.objects.get_or_create(key=key,defaults={'start':timezone.now()})
        bucket = RateBucket.objects.select_for_update().get(pk=key)
        if bucket.start < timezone.now()-timedelta(minutes=minutes):
            bucket.start,bucket.count = timezone.now(),0
        bucket.count += 1
        bucket.save()
        return bucket.count > maximum

def queue_invite(*,agency,email,name,role,actor,tenancy=None):
    Invitation.objects.filter(agency=agency,email__iexact=email,accepted_at=None,revoked_at=None).update(revoked_at=timezone.now())
    token = secrets.token_urlsafe(48)
    invitation = Invitation.objects.create(agency=agency,email=email,name=name,role=role,invited_by=actor,tenancy=tenancy,token_hash=digest(token),expires_at=timezone.now()+timedelta(hours=48))
    link = settings.SITE_URL+'/invitation/'+token+'/'
    MailQueue.objects.create(recipient=email,subject='Sevlink account invitation',body=f'Hello {name},\n\n{agency.name} has requested your {role} access to Sevlink.\nOpen this link within 48 hours:\n{link}\n\nIf unexpected, ignore this message.\nSevlink')
    return invitation
