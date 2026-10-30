from django.core.management.base import BaseCommand, CommandError
from portal.email_operations import resolve_feedback
from portal.models import User, OperationsFeedback


class Command(BaseCommand):
    help='Audited release of ONE negative-feedback suppression after manual deliverability investigation.'

    def add_arguments(self,parser):
        parser.add_argument('feedback',type=int)
        parser.add_argument('--actor',type=int,required=True)
        parser.add_argument('--reason',required=True)
        parser.add_argument('--confirmed-investigation',action='store_true')

    def handle(self,*args,**options):
        if not options['confirmed_investigation']:
            raise CommandError('Investigate the recipient/provider failure before confirming resolution.')
        try:
            resolve_feedback(options['feedback'],User.objects.get(pk=options['actor']),options['reason'])
        except (ValueError,User.DoesNotExist,OperationsFeedback.DoesNotExist):
            raise CommandError('Feedback resolution refused; check actor, event and reason.') from None
        self.stdout.write('Resolution audited; no mail sent or delivery claimed. Other unresolved feedback still suppresses delivery.')
