import time
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ImproperlyConfigured
from django.db import close_old_connections, connection
from portal.account_mail import deliver


class Command(BaseCommand):
    help='Leased account email worker. Live sending requires explicit SMTP activation; --preview never sends.'

    def add_arguments(self,parser):
        parser.add_argument('--preview',action='store_true')
        parser.add_argument('--watch',action='store_true')
        parser.add_argument('--interval',type=int,default=5)

    def handle(self,*args,**options):
        if not 1<=options['interval']<=60:
            raise CommandError('Interval must be 1–60 seconds.')
        while True:
            if not connection.in_atomic_block:
                close_old_connections()
            try:
                count=deliver(preview=options['preview'])
            except ImproperlyConfigured as error:
                raise CommandError(str(error)) from None
            self.stdout.write(f'{count} account message(s) accepted; previews are not deliveries.')
            if not options['watch']:
                break
            time.sleep(options['interval'])
