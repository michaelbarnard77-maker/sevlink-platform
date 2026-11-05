from django.db import migrations,models


def history(apps,schema_editor):
    Appointment=apps.get_model('portal','TeamAppointment')
    Appointment.objects.filter(cancelled_at__isnull=False).update(progress_status='cancelled')
    Appointment.objects.filter(cancelled_at__isnull=True,assignment__request__status__in=['completed','closed']).update(progress_status='completed')
    Job=apps.get_model('portal','MaintenanceRequest');Assignment=apps.get_model('portal','JobAssignment')
    for job in Job.objects.filter(status__in=['on_site','in_progress','attended']):
        current=Assignment.objects.filter(request=job).order_by('-created_at','-pk').first()
        if current:Appointment.objects.filter(assignment=current,cancelled_at__isnull=True).update(progress_status='on_site')


class Migration(migrations.Migration):
    dependencies=[('portal','0035_optional_assignment_city')]
    operations=[
        migrations.AddField(model_name='teamappointment',name='progress_status',field=models.CharField(choices=[('booked','Booked'),('on_site','On site'),('completed','Complete'),('cancelled','Cancelled')],default='booked',max_length=12)),
        migrations.AddField(model_name='teamappointment',name='version',field=models.PositiveIntegerField(default=1)),
        migrations.RunPython(history,migrations.RunPython.noop),
    ]
