from django.core.mail.backends.base import BaseEmailBackend
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from .models import MailQueue
class QueueBackend(BaseEmailBackend):
    def send_messages(self,email_messages):
        count = 0
        for message in email_messages:
            for recipient in message.to:
                MailQueue.objects.create(recipient=recipient,subject=message.subject,body=message.body,
                    expires_at=timezone.now()+timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT))
                count += 1
        return count


from pathlib import Path
import os
from django.conf import settings
from django.core.mail.backends.filebased import EmailBackend as FileBackend


class PrivatePreviewBackend(FileBackend):
    """Local testing messages, never a public outbox or real SMTP connection."""
    def __init__(self, *args, file_path=None, **kwargs):
        path = Path(file_path or settings.EMAIL_FILE_PATH)
        path.mkdir(parents=True, mode=0o700, exist_ok=True)
        super().__init__(*args, file_path=path, **kwargs)

    def open(self):
        if self.stream is None:
            descriptor = os.open(self._get_filename(), os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
            self.stream = os.fdopen(descriptor, 'ab')
            return True
        return False
