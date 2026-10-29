"""Local-only email operations contracts; no genuine SMTP delivery is exercised."""
import io
import json
import os
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from django.core import mail
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.management import call_command, CommandError
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from config.secrets import secret_value
from . import test_notifications as fixtures
from .checks import live_email_configuration
from .email_operations import feedback,replay,resolve_feedback
from .models import OperationsNotification,OperationsFeedback,OperationsFeedbackResolution,OperationsReplay,OperationsWorkerHeartbeat,OperationsDeliveryAttempt
from .notifications import deliver


@override_settings(SECURE_SSL_REDIRECT=False,ALLOWED_HOSTS=['testserver'],OPERATIONS_EMAIL_DELIVERY_BACKEND=fixtures.LOCAL,OPERATIONS_LIVE_DELIVERY_ENABLED=False)
class EmailReadinessTests(TestCase):
    setUpTestData=classmethod(fixtures.EventWorkflowTests.setUpTestData.__func__)
    post=fixtures.EventWorkflowTests.post
    new_job=fixtures.EventWorkflowTests.new_job

    def setUp(self):
        self.new_job(as_pm=True)
        self.item=OperationsNotification.objects.get()

    def event(self,kind):
        return dict(event_id=str(self.item.event_id),provider_event_id=str(__import__('uuid').uuid4()),kind=kind,occurred_at=timezone.now().isoformat())

    def test_local_worker_command_preserves_caller_owned_transaction(self):
        from django.db import connection
        self.assertTrue(connection.in_atomic_block)
        with patch('portal.management.commands.send_operations_notifications.close_old_connections') as cleanup:
            call_command('send_operations_notifications', stdout=io.StringIO())
            cleanup.assert_not_called()
        self.assertTrue(OperationsNotification.objects.filter(pk=self.item.pk).exists())
        self.assertEqual(OperationsNotification.objects.get(pk=self.item.pk).state, 'sent')
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(OPERATIONS_EMAIL_DELIVERY_BACKEND='django.core.mail.backends.smtp.EmailBackend',
                       OPERATIONS_LIVE_DELIVERY_ENABLED=True)
    def test_live_delivery_never_sends_from_an_uncommitted_transaction(self):
        with patch('portal.notifications.get_connection') as provider:
            with self.assertRaisesMessage(ImproperlyConfigured, 'outside a database transaction'):
                deliver()
            provider.assert_not_called()
        self.assertEqual(OperationsNotification.objects.get().attempts, 0)

    def test_mounted_secret_support_and_sanitized_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'secret';file.write_text('synthetic-test-value\n')
            with patch.dict(os.environ,{'SEVLINK_TEST_SECRET_FILE':str(file)},clear=False):
                self.assertEqual(secret_value('SEVLINK_TEST_SECRET'),'synthetic-test-value')
                with patch.dict(os.environ,{'SEVLINK_TEST_SECRET':'conflict'}):
                    with self.assertRaises(ImproperlyConfigured):secret_value('SEVLINK_TEST_SECRET')
            with patch.dict(os.environ,{'SEVLINK_TEST_SECRET_FILE':str(file)+'missing'}):
                with self.assertRaises(ImproperlyConfigured) as error:secret_value('SEVLINK_TEST_SECRET')
                self.assertNotIn(str(file),str(error.exception))

    @override_settings(OPERATIONS_EMAIL_DELIVERY_BACKEND='django.core.mail.backends.smtp.EmailBackend')
    def test_outbound_gate_refuses_smtp_before_any_connection(self):
        with patch('portal.notifications.get_connection') as provider:
            with self.assertRaises(ImproperlyConfigured):deliver()
            provider.assert_not_called()
        self.assertEqual(OperationsNotification.objects.get().attempts,0)

    @override_settings(OPERATIONS_LIVE_DELIVERY_ENABLED=True,OPERATIONS_EMAIL_DELIVERY_BACKEND='django.core.mail.backends.smtp.EmailBackend',EMAIL_HOST='',EMAIL_HOST_USER='',EMAIL_HOST_PASSWORD='')
    def test_live_config_check_requires_host_secrets_and_one_tls_mode(self):
        self.assertEqual(live_email_configuration(None)[0].id,'portal.E004')
        with override_settings(EMAIL_HOST='smtp.example.test',EMAIL_HOST_USER='synthetic',EMAIL_HOST_PASSWORD='synthetic',EMAIL_USE_TLS=True,EMAIL_USE_SSL=False):
            self.assertEqual(live_email_configuration(None),[])
            with override_settings(EMAIL_USE_SSL=True):self.assertTrue(live_email_configuration(None))

    @override_settings(OPERATIONS_SES_TAGGING_ENABLED=True)
    def test_local_message_has_stable_correlation_headers_and_worker_heartbeat(self):
        deliver()
        self.assertEqual(mail.outbox[0].extra_headers['X-Sevlink-Event'],str(self.item.event_id))
        self.assertIn(str(self.item.event_id),mail.outbox[0].extra_headers['X-SES-MESSAGE-TAGS'])
        self.assertTrue(OperationsWorkerHeartbeat.objects.get(name='operations').at)
        out=io.StringIO();call_command('operations_mail_status',stdout=out)
        self.assertEqual(json.loads(out.getvalue())['worker_stale'],False)
        self.assertNotIn('maintenance@',out.getvalue())

    def test_provider_feedback_is_idempotent_monotonic_and_retained_without_message_content(self):
        deliver();delivered=self.event('delivered');bounce=self.event('bounce')
        self.assertTrue(feedback(delivered));self.assertFalse(feedback(delivered))
        self.assertTrue(feedback(bounce))
        self.item.refresh_from_db();self.assertEqual(self.item.feedback_status,'bounce')
        self.assertEqual(OperationsFeedback.objects.count(),2)
        with self.assertRaises(ValueError):feedback(dict(delivered,kind='complaint'))
        with self.assertRaises(ValueError):feedback(dict(bounce,body='PRIVATE BODY'))
        self.assertEqual(set(OperationsFeedback.objects.values().first()),{'id','notification_id','provider_event_id','kind','occurred_at','created_at'})
        self.assertTrue(resolve_feedback(OperationsFeedback.objects.get(kind='bounce').pk,self.ops,'Recipient issue investigated externally'))
        self.item.refresh_from_db();self.assertEqual(self.item.feedback_status,'delivered')
        with self.assertRaises(ValidationError):OperationsFeedback.objects.first().delete()

    def test_negative_feedback_suppresses_future_recipient_mail_and_audited_resolution_releases(self):
        event=self.event('complaint');feedback(event)
        self.new_job(as_pm=True)
        self.assertEqual(deliver(),0)
        self.assertEqual(OperationsNotification.objects.filter(state='dead').count(),2)
        with self.assertRaises(ValueError):replay(self.item.pk,self.ops,'Cannot replay suppressed')
        record=OperationsFeedback.objects.get()
        with self.assertRaises(ValueError):resolve_feedback(record.pk,self.pm,'Forbidden')
        resolve_feedback(record.pk,self.ops,'Recipient/provider issue investigated')
        self.assertFalse(resolve_feedback(record.pk,self.ops,'Already resolved'))
        self.assertEqual(OperationsFeedbackResolution.objects.count(),1)
        replay(self.item.pk,self.ops,'Retry after confirmed resolution')
        self.assertEqual(deliver(),1)
        self.assertEqual(OperationsReplay.objects.count(),1)
        self.assertEqual(len(mail.outbox),1)

    def test_replay_preserves_attempt_numbers_and_limits_permissions(self):
        with patch('portal.notifications.get_connection',side_effect=OSError('PRIVATE ERROR')):
            for index in range(5):
                OperationsNotification.objects.update(next_attempt_at=timezone.now()-timedelta(seconds=1))
                deliver()
        self.item.refresh_from_db();self.assertEqual((self.item.state,self.item.attempts),('dead',5))
        with self.assertRaises(ValueError):replay(self.item.pk,self.pm,'Forbidden')
        replay(self.item.pk,self.ops,'SMTP problem investigated')
        self.item.refresh_from_db();self.assertEqual((self.item.attempts,self.item.retry_limit),(5,10))
        self.assertEqual(deliver(),1)
        self.assertEqual(list(OperationsDeliveryAttempt.objects.values_list('number',flat=True)),[1,2,3,4,5,6])
        with self.assertRaises(ValueError):replay(self.item.pk,self.ops,'Already sent')

    def test_feedback_import_requires_trusted_verification_and_health_reports_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'event.json';file.write_text(json.dumps(self.event('bounce')))
            with self.assertRaises(CommandError):call_command('import_operations_feedback',str(file),stdout=io.StringIO())
            call_command('import_operations_feedback',str(file),verified=True,stdout=io.StringIO())
        with self.assertRaises(CommandError):call_command('operations_mail_status',fail_if_unhealthy=True,stdout=io.StringIO())
        record=OperationsFeedback.objects.get()
        with self.assertRaises(CommandError):call_command('resolve_operations_feedback',record.pk,actor=self.ops.pk,reason='Reviewed',stdout=io.StringIO())
        call_command('resolve_operations_feedback',record.pk,actor=self.ops.pk,reason='Reviewed',confirmed_investigation=True,stdout=io.StringIO())


@override_settings(OPERATIONS_EMAIL_DELIVERY_BACKEND=fixtures.LOCAL, OPERATIONS_LIVE_DELIVERY_ENABLED=False)
class WorkerConnectionLifecycleTests(TransactionTestCase):
    def test_standalone_worker_refreshes_connections_between_committed_batches(self):
        from django.db import connection, close_old_connections
        self.assertFalse(connection.in_atomic_block)
        with patch('portal.management.commands.send_operations_notifications.close_old_connections',
                   wraps=close_old_connections) as cleanup:
            call_command('send_operations_notifications', stdout=io.StringIO())
            cleanup.assert_called_once()
        self.assertTrue(OperationsWorkerHeartbeat.objects.filter(name='operations').exists())
