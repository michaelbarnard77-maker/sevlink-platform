from django.core.mail.backends.base import BaseEmailBackend
from .models import MailQueue
class QueueBackend(BaseEmailBackend):
    def send_messages(self,email_messages):
        count = 0
        for message in email_messages:
            for recipient in message.to:
                MailQueue.objects.create(recipient=recipient,subject=message.subject,body=message.body)
                count += 1
        return count
