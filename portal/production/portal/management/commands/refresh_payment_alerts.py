from django.core.management.base import BaseCommand, CommandError
from portal.models import User
from portal.workflow import refresh_overdue

class Command(BaseCommand):
    help='Persist deduplicated overdue supplier invoice alerts; no payments or emails are sent.'
    def handle(self,*args,**kwargs):
        actor=User.objects.filter(is_active=True,is_superuser=True).order_by('pk').first()
        if not actor:raise CommandError('An active Super Admin is required.')
        self.stdout.write(f'Reviewed overdue supplier invoices: {refresh_overdue(actor)}')
