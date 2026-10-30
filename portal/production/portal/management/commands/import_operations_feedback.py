import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from portal.email_operations import feedback
from portal.models import OperationsNotification


class Command(BaseCommand):
    help='Import one trusted normalized provider event AFTER external signature/account verification.'

    def add_arguments(self,parser):
        parser.add_argument('file')
        parser.add_argument('--verified',action='store_true')

    def handle(self,*args,**options):
        if not options['verified']:
            raise CommandError('Verify provider signature, account, topic and recipients before using --verified.')
        try:
            path=Path(options['file'])
            if path.stat().st_size>16384:raise ValueError()
            changed=feedback(json.loads(path.read_text()))
        except (OSError,ValueError,TypeError,OperationsNotification.DoesNotExist):
            raise CommandError('Invalid or unmatched trusted provider feedback; no secrets/content logged.') from None
        self.stdout.write('Feedback recorded.' if changed else 'Feedback already recorded; no duplicate.')
