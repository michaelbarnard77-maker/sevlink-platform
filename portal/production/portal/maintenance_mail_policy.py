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
