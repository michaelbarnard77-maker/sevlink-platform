"""Explicit one-message SMTP test; does not read queues or persist credentials."""
from getpass import getpass
from django.core.management.base import BaseCommand, CommandError
from django.core.mail import get_connection
from portal.email_branding import BrandedEmail, branded_bodies


class Command(BaseCommand):
    help = 'Send one signed test email only; does not process any queued mail.'

    def add_arguments(self, parser):
        parser.add_argument('--to', required=True)

    def handle(self, *args, **options):
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError
        try:
            validate_email(options['to'])
        except ValidationError:
            raise CommandError('Enter a valid recipient email address.')
        username = input('SMTP username: ').strip()
        password = getpass('SMTP password (hidden): ')
        body = ('Hello,\n\nThis is a test of Sevlink’s automatic email signature.\n'
                'No queued invitations or notifications have been sent.\n\n'
                'Please check that the signature below displays correctly.')
        plain, html = branded_bodies(body)
        try:
            with get_connection('django.core.mail.backends.smtp.EmailBackend',
                                host='mail.bulkmail-za.com', port=5878, username=username,
                                password=password, use_tls=True, use_ssl=False, timeout=30) as connection:
                message = BrandedEmail('Sevlink signature test', plain,
                                       'Sevlink <maintenance@sevlink.co.za>', [options['to']], connection=connection)
                message.attach_alternative(html, 'text/html')
                if message.send() != 1:
                    raise OSError()
        except Exception:
            raise CommandError('Test email failed. Check SMTP details and connectivity; credentials have not been saved.') from None
        self.stdout.write(self.style.SUCCESS('SUCCESS: SMTP server accepted one signed test email. Check the recipient inbox.'))
