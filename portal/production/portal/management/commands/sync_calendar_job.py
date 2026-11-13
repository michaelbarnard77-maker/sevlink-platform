"""Repair one existing job whose calendar progress predates automatic syncing."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from portal.models import MaintenanceRequest, Property, User, TeamAppointment
from portal.calendar_sync import progress_plan, sync_job

class Command(BaseCommand):
    help = 'Preview or apply calendar progress to one job. Defaults to a read-only preview.'

    def add_arguments(self, parser):
        parser.add_argument('--reference',required=True)
        parser.add_argument('--apply',action='store_true')

    def handle(self,*args,**options):
        import re
        match=re.fullmatch(r'SV-(\d+)',options['reference'].upper())
        if not match:
            raise CommandError('Use an official job reference, for example SV-0001.')
        job=MaintenanceRequest.objects.filter(job_number=int(match[1])).first()
        if not job:
            raise CommandError('Job reference not found.')
        if not TeamAppointment.objects.filter(assignment__request=job,cancelled_at=None,progress_status='completed').exists():
            raise CommandError('No completed calendar visit exists for this job. No changes made.')
        actor=User.objects.filter(is_superuser=True,is_active=True).order_by('pk').first()
        if not actor:
            raise CommandError('An active Sevlink administrator is required.')
        with transaction.atomic():
            Property.objects.select_for_update().get(pk=job.property_id)
            job=MaintenanceRequest.objects.select_for_update().get(pk=job.pk)
            before=job.status
            desired,assessment_done=progress_plan(job,'completed')
            if not options['apply']:
                self.stdout.write(f'{job.reference}: {before} -> {desired} (preview only; no changes made)')
                return
            changed=sync_job(job,actor,'completed')
            from portal.workflow import stage
            self.stdout.write(f'{job.reference}: {before} -> {job.status}; pot: {stage(job)}; '+('updated' if changed else 'already in sync'))
