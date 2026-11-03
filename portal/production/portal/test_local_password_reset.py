import io
from unittest.mock import patch
from django.core.management import call_command, CommandError
from django.test import TestCase
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from .models import User, MailQueue


class LocalPasswordResetTests(TestCase):
    def test_one_account_local_token_and_targeted_dispatch(self):
        user=User.objects.create_user(username='agency@example.test',email='agency@example.test',password='Original-test-password!')
        older=MailQueue.objects.create(recipient='other@example.test',subject='Unrelated',body='private')
        with patch('portal.management.commands.send_local_password_reset.input',return_value='synthetic-user'), patch('portal.management.commands.send_local_password_reset.getpass',return_value='synthetic-secret'), patch('portal.management.commands.send_local_password_reset.deliver',return_value=1) as sender:
            out=io.StringIO();call_command('send_local_password_reset',to=user.email,stdout=out)
        selected=MailQueue.objects.exclude(pk=older.pk).get()
        sender.assert_called_once_with(limit=1,message_id=selected.pk)
        self.assertEqual(selected.recipient,user.email)
        token=selected.body.split('/password/reset/')[1].strip().split('/')[1]
        self.assertTrue(default_token_generator.check_token(user,token))
        self.assertIn('http://127.0.0.1:8000'+reverse('password_reset_confirm',args=[urlsafe_base64_encode(force_bytes(user.pk)),token]),selected.body)
        user.refresh_from_db();self.assertTrue(user.check_password('Original-test-password!'))
        older.refresh_from_db();self.assertEqual(older.attempts,0)
        self.assertNotIn(token,out.getvalue());self.assertNotIn('synthetic-secret',out.getvalue())

    def test_missing_account_refuses_before_prompt_or_queue(self):
        with patch('portal.management.commands.send_local_password_reset.getpass') as prompt:
            with self.assertRaises(CommandError):call_command('send_local_password_reset',to='unknown@example.test',stdout=io.StringIO())
            prompt.assert_not_called()
        self.assertEqual(MailQueue.objects.count(),0)
