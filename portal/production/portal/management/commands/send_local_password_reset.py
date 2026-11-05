"""Explicit single-account local reset; never runs a queue worker or saves SMTP credentials."""
from datetime import timedelta
from getpass import getpass
from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.template.loader import render_to_string
from django.test.utils import override_settings
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from portal.account_mail import deliver
from portal.models import MailQueue


class Command(BaseCommand):
    help = 'Send one local-only password reset. Link opens on the computer running Sevlink; no backlog is sent.'

    def add_arguments(self, parser):
        parser.add_argument('--to', required=True)

    def handle(self, *args, **options):
        email = options['to'].strip()
        try:
            validate_email(email)
        except ValidationError:
            raise CommandError('Enter a valid recipient email address.')
        users = list(PasswordResetForm().get_users(email))
        if len(users) != 1:
            raise CommandError('Exactly one active account with a usable password is required. No email sent; check the account first.')
        user = users[0]
        self.stdout.write('Recipient: ' + user.email)
        self.stdout.write('Link address: http://127.0.0.1:8000 (same computer only).')
        username = input('Bulk SMTP username: ').strip()
        password = getpass('Bulk SMTP password (hidden): ')
        if not username or not password:
            raise CommandError('SMTP credentials required. Nothing queued or sent.')
        context = dict(email=user.email, user=user, domain='127.0.0.1:8000', site_name='Sevlink',
                       protocol='http', uid=urlsafe_base64_encode(force_bytes(user.pk)),
                       token=default_token_generator.make_token(user))
        body = render_to_string('registration/password_reset_email.txt', context)
        subject = ''.join(render_to_string('registration/password_reset_subject.txt', context).splitlines())
        item = MailQueue.objects.create(recipient=user.email, subject=subject, body=body,
                                       expires_at=timezone.now()+timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT))
        with override_settings(SMTP_DELIVERY_ENABLED=True, OPERATIONS_LIVE_DELIVERY_ENABLED=False,
                               EMAIL_HOST='mail.bulkmail-za.com', EMAIL_PORT=5878,
                               EMAIL_HOST_USER=username, EMAIL_HOST_PASSWORD=password,
                               EMAIL_USE_TLS=True, EMAIL_USE_SSL=False,
                               DEFAULT_FROM_EMAIL='Sevlink <maintenance@sevlink.co.za>'):
            count = deliver(limit=1, message_id=item.pk)
        if count != 1:
            raise CommandError('Reset email was not accepted. Check SMTP credentials/connectivity. No other queued mail was processed.')
        self.stdout.write(self.style.SUCCESS('SUCCESS: One password-reset email accepted. Start Sevlink and open the email link on this computer.'))
