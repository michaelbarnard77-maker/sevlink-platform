from django.core.management.base import BaseCommand, CommandError
from django.core.mail import EmailMessage, get_connection
from django.db import transaction
from django.conf import settings
from django.utils import timezone
from portal.models import MailQueue
class Command(BaseCommand):
    help = 'Deliver queued email. Disabled until SMTP delivery is explicitly enabled.'
    def handle(self,*args,**options):
        if not settings.SMTP_DELIVERY_ENABLED or not settings.EMAIL_HOST:
            raise CommandError('SMTP delivery disabled. Configure and verify sender before enabling.')
        connection = get_connection('django.core.mail.backends.smtp.EmailBackend')
        for pk in list(MailQueue.objects.filter(sent_at=None,attempts__lt=5).order_by('pk').values_list('pk',flat=True)[:50]):
            with transaction.atomic():
                message = MailQueue.objects.select_for_update().get(pk=pk)
                if message.sent_at:
                    continue
                message.attempts += 1
                try:
                    EmailMessage(message.subject,message.body,to=[message.recipient],connection=connection).send(fail_silently=False)
                except Exception:
                    self.stderr.write(f'Queue item {pk}: delivery failed; retry pending.')
                else:
                    message.sent_at = timezone.now()
                    message.body = '[Delivered; invitation content removed]'
                message.save()
