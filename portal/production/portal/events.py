"""Central durable event/outbox interface. Called inside successful business transactions."""
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import JobActivity, OperationsNotification, OperationsInboxItem


def actor_identity(user):
    if user.is_superuser:
        role = 'superadmin'
    else:
        membership = getattr(user, 'membership', None)
        role = membership.role if membership else 'unknown'
    label = {'superadmin': 'Sevlink Operations', 'tenant': 'Tenant', 'pm': 'Property manager', 'admin': 'Agency administrator'}.get(role, 'User')
    return role, user.get_full_name()[:300] or label


def record(job, actor, kind, dedup_key, details=None, *, private=False):
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError('Job events must share the business transaction.')
    if kind not in JobActivity.Kind.values:
        raise ValueError('Unsupported job event.')
    role, name = actor_identity(actor)
    fields = {
        'job_submitted': {'status'}, 'status_changed': {'status'}, 'job_cancelled': {'status'}, 'job_completed': {'status'},
        'comment_added': {'comment_id', 'text'}, 'quote_created': {'quote_id', 'title', 'amount'},
        'quote_approved': {'quote_id', 'amount', 'status', 'reason'}, 'quote_rejected': {'quote_id', 'amount', 'status', 'reason'},
    }
    fields.update({kind: {'quote_id', 'amount', 'status', 'reason'} for kind in ('quote_edited', 'quote_sent', 'quote_revised', 'quote_superseded', 'quote_revision_requested')})
    fields.update({kind: {'invoice_id','number','amount','status'} for kind in ('invoice_uploaded','invoice_payment')})
    fields.update({'conversation_permission': {'tenant_comments_allowed'}, 'internal_note': {'comment_id', 'text'}, 'notification_state': {'notification_id', 'read'}})
    if set(details or {}) != fields[kind] or any(not isinstance(value, str) for value in (details or {}).values()):
        raise ValueError('Unexpected event detail fields.')
    event, created = JobActivity.objects.get_or_create(dedup_key=dedup_key, defaults={
        'request': job, 'actor': actor, 'actor_name': name, 'actor_role': role, 'kind': kind,
        'details': details or {}, 'job_title': job.title,
        'visibility': 'internal' if private or kind in ('conversation_permission', 'internal_note', 'quote_created', 'quote_edited', 'quote_revised', 'notification_state') else 'shared',
        'property_name': job.property.name, 'property_address': job.property.address,
        'agency_name': job.property.agency.name,
    })
    if not created and (event.request_id != job.pk or event.actor_id != actor.pk or event.kind != kind or event.details != (details or {}) or (private and event.visibility != 'internal')):
        raise ValueError('Event key conflicts with an existing event.')
    notify_kinds = {JobActivity.Kind.SUBMITTED, JobActivity.Kind.COMMENT, JobActivity.Kind.QUOTE_APPROVED,
                    JobActivity.Kind.QUOTE_REJECTED, JobActivity.Kind.QUOTE_REVISION, JobActivity.Kind.CANCELLED, JobActivity.Kind.COMPLETED}
    should_notify = kind in notify_kinds and (kind != JobActivity.Kind.COMMENT or role in ('tenant', 'pm', 'admin'))
    if created and should_notify:
        OperationsNotification.objects.create(event=event, recipient=settings.OPERATIONS_NOTIFICATION_EMAIL)
        OperationsInboxItem.objects.create(event=event)
    return event


def activity_data(event, user):
    if event.actor_role == 'superadmin' and not user.is_superuser:
        actor = 'Sevlink Operations'
    else:
        actor = event.actor_name
    # Actor IDs/email addresses and internal user identities are deliberately absent.
    return {'id': str(event.pk), 'type': event.kind, 'label': event.get_kind_display(),
            'actor': actor, 'at': event.created_at.isoformat(), 'details': event.details}


def notification_message(event):
    # Operations-only summary: no comment bodies, tenant email/phone, private access
    # notes, attachment filenames/contents, internal notes or subcontractor fields.
    details = event.details
    one_line = lambda value: ' '.join(str(value).split())
    if event.kind == JobActivity.Kind.SUBMITTED:
        summary = 'New report: ' + one_line(event.job_title)
    elif event.kind == JobActivity.Kind.COMMENT:
        summary = 'A shared comment was added. Sign in to read the comment.'
    elif event.kind in (JobActivity.Kind.QUOTE_APPROVED, JobActivity.Kind.QUOTE_REJECTED, JobActivity.Kind.QUOTE_REVISION):
        summary = f'Quotation {details["quote_id"]}: ZAR {details["amount"]}; {details["status"]}.'
    else:
        summary = 'Job status: ' + details.get('status', event.kind)
    link = settings.SITE_URL + reverse('maintenance_workspace') + '?' + urlencode({'job': str(event.request_id)})
    body = '\n'.join([
        f'Job: SV-{str(event.request_id).upper()}', f'Property: {one_line(event.property_name)}',
        f'Address: {one_line(event.property_address)}', f'Agency: {one_line(event.agency_name)}',
        f'Event: {event.get_kind_display()}', f'Details: {summary}',
        f'Actor role: {event.actor_role}', f'Timestamp: {timezone.localtime(event.created_at).isoformat()}',
        '', 'Sign in with your authorized Sevlink account:', link,
        '', 'This link does not grant access or contain a login token.',
    ])
    subject = f'Sevlink SV-{str(event.request_id).upper()} — {event.get_kind_display()}'
    return subject, body
