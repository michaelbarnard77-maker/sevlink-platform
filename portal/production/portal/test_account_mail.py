import tempfile
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, override_settings, TransactionTestCase
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from .account_mail import deliver
from .models import MailQueue, AccountMailAttempt

class AccountMailTests(TestCase):
    def setUp(self):
        self.item=MailQueue.objects.create(recipient='synthetic@example.test',subject='Test invitation',body='Private test link')

    def test_preview_never_consumes_or_sends_live_queue(self):
        with tempfile.TemporaryDirectory() as directory, override_settings(EMAIL_FILE_PATH=directory):
            self.assertEqual(deliver(preview=True),0)
        self.item.refresh_from_db()
        self.assertIsNone(self.item.sent_at);self.assertEqual(self.item.attempts,0)
        self.assertEqual(self.item.body,'Private test link')
        self.assertEqual(AccountMailAttempt.objects.get().outcome,'preview')

    def test_failures_retry_without_losing_message(self):
        with patch('portal.account_mail.get_connection',side_effect=OSError): deliver(preview=True)
        self.item.refresh_from_db()
        self.assertEqual(self.item.attempts,1);self.assertEqual(self.item.error_code,'delivery_failed')
        self.assertIsNone(self.item.lease_token);self.assertIsNone(self.item.sent_at)
        self.assertGreater(self.item.next_attempt_at,timezone.now())

    def test_expired_message_is_not_sent_and_token_is_removed(self):
        self.item.expires_at=timezone.now()-timedelta(seconds=1);self.item.save()
        with patch('portal.account_mail.get_connection') as provider: deliver(preview=True)
        provider.assert_not_called();self.item.refresh_from_db()
        self.assertEqual(self.item.error_code,'expired');self.assertNotIn('Private',self.item.body)

    def test_live_delivery_refuses_uncommitted_transactions(self):
        with self.assertRaises(ImproperlyConfigured): deliver()

@override_settings(SMTP_DELIVERY_ENABLED=True,EMAIL_HOST='test.invalid',EMAIL_HOST_USER='synthetic',EMAIL_HOST_PASSWORD='synthetic',EMAIL_USE_TLS=True,EMAIL_USE_SSL=False)
class AccountMailCommittedTests(TransactionTestCase):
    def test_mock_provider_only_accepts_saved_message_once(self):
        item=MailQueue.objects.create(recipient='synthetic@example.test',subject='Test',body='test link')
        with patch('portal.account_mail.get_connection') as provider:
            provider.return_value.send_messages.return_value=1
            self.assertEqual(deliver(),1);self.assertEqual(deliver(),0)
            self.assertEqual(provider.return_value.send_messages.call_count,1)
        item.refresh_from_db();self.assertIsNotNone(item.sent_at)
        self.assertEqual(AccountMailAttempt.objects.get().outcome,'accepted')

from unittest import skipUnless
from concurrent.futures import ThreadPoolExecutor
from django.db import connection, connections


@skipUnless(connection.vendor=='postgresql','PostgreSQL outbox locking test')
@override_settings(SMTP_DELIVERY_ENABLED=True,EMAIL_HOST='test.invalid',EMAIL_HOST_USER='synthetic',EMAIL_HOST_PASSWORD='synthetic',EMAIL_USE_TLS=True,EMAIL_USE_SSL=False)
class AccountMailConcurrencyTests(TransactionTestCase):
    def test_two_workers_claim_one_saved_message_once(self):
        item=MailQueue.objects.create(recipient='synthetic@example.test',subject='Synthetic',body='Synthetic committed link')
        def work(_):
            try:return deliver()
            finally:connections.close_all()
        with patch('portal.account_mail.get_connection') as provider:
            provider.return_value.send_messages.return_value=1
            with ThreadPoolExecutor(max_workers=2) as pool:counts=list(pool.map(work,[1,2]))
            self.assertEqual(sum(counts),1)
            self.assertEqual(provider.return_value.send_messages.call_count,1)
        item.refresh_from_db();self.assertEqual(item.attempts,1)
        self.assertEqual(AccountMailAttempt.objects.count(),1)
