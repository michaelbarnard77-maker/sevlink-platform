from django.db import migrations, models


def pending_unstarted(apps, schema_editor):
    Request=apps.get_model('portal','MaintenanceRequest')
    Request.objects.filter(status__in=['awaiting_review','reviewed'],closed_at=None,
                           invoices__isnull=True,attendance_requests__isnull=True,
                           scheduling_arrangements__isnull=True,workflow_version=1).update(jobs_payment_route='pending')


class Migration(migrations.Migration):
    dependencies=[('portal','0036_appointment_progress')]
    operations=[
        migrations.AddField(model_name='maintenancerequest',name='jobs_payment_route',field=models.CharField(choices=[('legacy','Existing terms'),('pending','Sevlink decision required'),('deposit','50% deposit required'),('without_deposit','Start without deposit')],default='legacy',editable=False,max_length=16)),
        migrations.RunPython(pending_unstarted,migrations.RunPython.noop),
    ]
