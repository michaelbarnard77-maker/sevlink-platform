import time

from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ImproperlyConfigured
from portal.notifications import deliver
from django.db import close_old_connections


class Command(BaseCommand):
    help = 'Process saved Operations events through the configured delivery backend (local file preview by default).'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=50)
        parser.add_argument('--watch', action='store_true')
        parser.add_argument('--interval', type=int, default=5)

    def handle(self, *args, **options):
        if not 1 <= options['limit'] <= 500:
            raise CommandError('Limit must be between 1 and 500.')
        if not 1 <= options['interval'] <= 60:
            raise CommandError('Interval must be between 1 and 60 seconds.')
        try:
            while True:
                close_old_connections()
                count = deliver(options['limit'])
                self.stdout.write(f'Processed {count} Operations delivery attempts. Inspect outbox state for pending/failed records.')
                if not options['watch']:
                    break
                time.sleep(options['interval'])
        except ImproperlyConfigured as error:
            raise CommandError(str(error))
        except KeyboardInterrupt:
            self.stdout.write('Operations delivery worker stopped.')
