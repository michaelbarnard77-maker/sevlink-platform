import json
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone
from portal.models import MailQueue, OperationsWorkerHeartbeat


class Command(BaseCommand):
    help='Sanitized account-email health; no bodies, links or recipients.'

    def add_arguments(self,parser):
        parser.add_argument('--fail-if-unhealthy',action='store_true')

    def handle(self,*args,**options):
        now=timezone.now();cutoff=now-timedelta(minutes=5)
        pending=MailQueue.objects.filter(sent_at=None,retired_at=None)
        beat=OperationsWorkerHeartbeat.objects.filter(name='accounts').first()
        data={'pending':pending.count(),'failed':pending.filter(attempts__gte=5).count(),
              'worker_stale':not beat or beat.at<cutoff,
              'overdue':pending.filter(created_at__lt=cutoff).count(),
              'expired_leases':pending.filter(lease_expires_at__lt=now).exclude(lease_token=None).count()}
        self.stdout.write(json.dumps(data,sort_keys=True))
        if options['fail_if_unhealthy'] and any(data[k] for k in ('failed','worker_stale','overdue','expired_leases')):
            raise CommandError('Account email monitoring requires attention.')
