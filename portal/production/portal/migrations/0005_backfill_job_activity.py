from django.db import migrations


def backfill(apps, schema_editor):
    Event = apps.get_model('portal', 'JobActivity')
    Status = apps.get_model('portal', 'MaintenanceStatusEvent')
    Membership = apps.get_model('portal', 'Membership')
    roles = dict(Membership.objects.values_list('user_id', 'role'))
    for status in Status.objects.select_related('actor', 'request__property__agency').order_by('at', 'id').iterator():
        job, actor = status.request, status.actor
        role = 'superadmin' if actor.is_superuser else roles.get(actor.pk, 'unknown')
        kind = {'awaiting_review': 'job_submitted', 'completed': 'job_completed', 'cancelled': 'job_cancelled'}.get(status.status, 'status_changed')
        name = (actor.first_name + ' ' + actor.last_name).strip() or role
        Event.objects.get_or_create(dedup_key=f'legacy-status:{status.pk}', defaults={
            'request_id': job.pk, 'actor_id': actor.pk, 'actor_name': name[:300], 'actor_role': role,
            'kind': kind, 'details': {'status': status.status}, 'job_title': job.title,
            'property_name': job.property.name, 'property_address': job.property.address,
            'agency_name': job.property.agency.name, 'created_at': status.at,
        })
    # Deliberately no OperationsNotification rows: do not email historical activity on upgrade.


class Migration(migrations.Migration):
    dependencies = [('portal', '0004_jobactivity_jobcomment_operationsnotification_and_more')]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
