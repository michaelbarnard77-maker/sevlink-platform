from django.core.management.base import BaseCommand, CommandError
from portal.email_operations import replay
from portal.models import User, OperationsNotification


class Command(BaseCommand):
    help='Audited Operations-only dead-letter replay; preserves attempts and Message-ID.'

    def add_arguments(self,parser):
        parser.add_argument('notification',type=int)
        parser.add_argument('--actor',required=True,type=int)
        parser.add_argument('--reason',required=True)

    def handle(self,*args,**options):
        try:
            replay(options['notification'],User.objects.get(pk=options['actor']),options['reason'])
        except (ValueError,User.DoesNotExist,OperationsNotification.DoesNotExist):
            raise CommandError('Replay refused: check failure state, suppression, actor and reason.') from None
        self.stdout.write('Replay queued; original attempt history retained. Delivery remains subject to the live-delivery gate.')
