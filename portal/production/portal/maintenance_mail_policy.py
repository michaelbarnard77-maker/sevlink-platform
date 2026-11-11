"""Maintenance email is reserved for incoming work and actionable customer updates."""
from .models import InvoiceAction


def maintenance_email_allowed(event):
    if event.kind=='job_submitted':
        # Tenant reports reach their PM first; the forward/review event alerts Sevlink.
        return event.actor_role in ('pm','admin')
    if event.kind=='quote_approved':
        return True
    if event.kind=='comment_added':
        return event.actor_role in ('tenant','pm','admin','client') and event.visibility!='internal'
    if event.kind!='workflow_event':
        return False
    if event.dedup_key.startswith('payment-reported:'):
        try:
            return InvoiceAction.objects.filter(pk=event.details.get('decision_id'),kind='payment_reported',
                invoice__request_id=event.request_id,invoice__visibility='shared',invoice__subcontractor__isnull=True,
                invoice__purpose__in=('deposit','final','legacy')).exists()
        except (ValueError,TypeError):
            return False
    if event.details.get('action')=='Request reviewed and routed' and event.actor_role in ('pm','admin'):
        if event.request.activities.filter(kind='job_submitted',actor_role__in=('pm','admin')).exists():
            return False
        first=event.request.activities.filter(kind='workflow_event',details__action='Request reviewed and routed').order_by('created_at','pk').first()
        return first is not None and first.pk==event.pk
    return False


def assigned_pm(event):
    """Only the active PM currently assigned within this property's agency."""
    job=event.request
    if job.private_client_id:return None
    pm=job.property.manager
    if not pm or not pm.is_active or not pm.email:return None
    from .models import Membership
    if not Membership.objects.filter(user=pm,agency_id=job.property.agency_id,role=Membership.PM).exists():return None
    return pm


def pm_email_allowed(event):
    # Tenant reports reach the PM before Sevlink reviews/receives the work.
    if event.kind=='job_submitted':return event.actor_role in ('tenant','pm','admin')
    # Payment reports and routing are private workflow events containing only a
    # safe action summary. Never copy internal notes or supplier information.
    return maintenance_email_allowed(event)


def email_allowed_for_recipient(notification):
    from django.conf import settings
    if notification.recipient.casefold()==settings.OPERATIONS_NOTIFICATION_EMAIL.casefold():
        return maintenance_email_allowed(notification.event)
    pm=assigned_pm(notification.event)
    return bool(pm and pm.email.casefold()==notification.recipient.casefold() and pm_email_allowed(notification.event))
