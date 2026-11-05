import json
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Min
from django.utils import timezone
from portal.models import OperationsNotification, OperationsWorkerHeartbeat, OperationsFeedback


class Command(BaseCommand):
    help='Private email queue health summary; contains no recipients, bodies or credentials.'

    def add_arguments(self,parser):
        parser.add_argument('--fail-if-unhealthy',action='store_true')
        parser.add_argument('--max-age',type=int,default=300)

    def handle(self,*args,**options):
        if not 30<=options['max_age']<=86400:
            raise CommandError('Max age must be 30–86400 seconds.')
        cutoff=timezone.now()-timedelta(seconds=options['max_age'])
        beat=OperationsWorkerHeartbeat.objects.filter(name='operations').first()
        counts={state:OperationsNotification.objects.filter(state=state).count() for state in ('pending','sending','sent','dead')}
        oldest=OperationsNotification.objects.filter(state='pending').aggregate(at=Min('created_at'))['at']
        summary=dict(counts,worker_stale=not beat or beat.at<cutoff,
            pending_overdue=bool(oldest and oldest<cutoff),negative_feedback=OperationsFeedback.objects.filter(kind__in=['bounce','complaint'],resolution__isnull=True).count(),
            expired_leases=OperationsNotification.objects.filter(state='sending',lease_expires_at__lt=timezone.now()).count())
        self.stdout.write(json.dumps(summary,sort_keys=True))
        if options['fail_if_unhealthy'] and (summary['worker_stale'] or summary['pending_overdue'] or summary['negative_feedback'] or summary['expired_leases'] or counts['dead']):
            raise CommandError('Operations email monitoring requires attention.')
