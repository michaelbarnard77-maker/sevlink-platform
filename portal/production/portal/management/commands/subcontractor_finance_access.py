from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand, CommandError
from portal.models import User


class Command(BaseCommand):
    help = 'Explicitly grant/revoke private subcontractor bank access for an active Operations account.'

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True)
        parser.add_argument('--revoke', action='store_true')

    def handle(self, *args, **options):
        user = User.objects.filter(email__iexact=options['email'], is_active=True, is_superuser=True).first()
        if not user:
            raise CommandError('An active Sevlink Super Admin account is required.')
        permission = Permission.objects.get(content_type__app_label='portal',content_type__model='subcontractor',codename='manage_subcontractor_finance')
        if options['revoke']: user.user_permissions.remove(permission)
        else: user.user_permissions.add(permission)
        self.stdout.write('Explicit subcontractor finance permission updated. Group grants, if any, are managed separately.')
