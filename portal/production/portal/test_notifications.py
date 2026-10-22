import io
import json
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.db import transaction, connection
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .test_attachments import document
from .checks import operations_configuration
from .events import record, notification_message
from .models import (Agency, Audit, JobActivity, JobComment, JobQuotation, MaintenanceRequest,
                     Membership, OperationsNotification, OperationsDeliveryAttempt, Property, Tenancy, User)
from .notifications import claim, deliver

LOCAL = 'django.core.mail.backends.locmem.EmailBackend'


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False,
                   ALLOWED_HOSTS=['testserver'], OPERATIONS_NOTIFICATION_EMAIL='maintenance@sevlink.co.za',
                   OPERATIONS_EMAIL_DELIVERY_BACKEND=LOCAL, OPERATIONS_LIVE_DELIVERY_ENABLED=False)
class EventWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.agency = Agency.objects.create(name='Event Agency A', phone='test', area='Test')
        cls.foreign_agency = Agency.objects.create(name='Event Agency B', phone='test', area='Test')
        def user(name, role=None, agency=None, **flags):
            u = User.objects.create_user(username=name+'@example.test', email=name+'@example.test', first_name=name, **flags)
            if role:
                Membership.objects.create(user=u, agency=agency or cls.agency, role=role)
            return u
        cls.tenant = user('event-tenant', 'tenant')
        cls.pm = user('event-pm', 'pm')
        cls.admin = user('event-admin', 'admin')
        cls.other_pm = user('event-other-pm', 'pm')
        cls.foreign = user('event-foreign', 'pm', cls.foreign_agency)
        cls.cotenant = user('event-cotenant', 'tenant')
        cls.ops = user('PRIVATE-STAFF-NAME', is_staff=True, is_superuser=True)
        cls.home = Property.objects.create(agency=cls.agency, manager=cls.pm, name='Event Home', address='Example address', access_notes='PRIVATE ACCESS CODE')
        for tenant in [cls.tenant, cls.cotenant]:
            Tenancy.objects.create(property=cls.home, user=tenant, name=tenant.first_name, email=tenant.email, phone='PRIVATE PHONE')
        cls.collection = reverse('maintenance_collection')

    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='sevlink-commercial-test-')
        self.addCleanup(directory.cleanup)
        aliases = {**settings.STORAGES, 'maintenance_private': {
            'BACKEND': 'portal.attachment_storage.PrivateAttachmentStorage', 'OPTIONS': {'location': directory.name}}}
        override = override_settings(PRIVATE_ATTACHMENT_ROOT=directory.name, STORAGES=aliases)
        override.enable(); self.addCleanup(override.disable)

    def upload_quote(self, key=None):
        return self.client.post(self.quote_url, {'reference':('Q-TEST-'+str(key)) if key else 'Q-TEST-'+str(JobQuotation.objects.count()+1), 'title':'Repair quotation',
            'scope':'Replace the leaking tap.', 'amount':'1250.50', 'attachments':document(name='quotation.pdf')},
            HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))

    def post(self, url, body, key=None):
        return self.client.post(url, json.dumps(body), content_type='application/json', HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))

    def new_job(self, key=None):
        self.client.force_login(self.tenant)
        response = self.post(self.collection, {'property': str(self.home.pk), 'title': 'Kitchen repair',
            'description': 'Private tenant description', 'category': 'Plumbing'}, key)
        self.assertEqual(response.status_code, 201, response.content)
        self.job = MaintenanceRequest.objects.get(pk=response.json()['id'])
        MaintenanceRequest.objects.filter(pk=self.job.pk).update(workflow_version=0)
        self.job.refresh_from_db()
        self.detail_url = reverse('maintenance_detail', args=[self.job.pk])
        self.comment_url = reverse('maintenance_comment', args=[self.job.pk])
        self.quote_url = reverse('maintenance_quote', args=[self.job.pk])
        return self.job

    def new_quote(self, key=None):
        self.client.force_login(self.ops)
        response = self.upload_quote(key)
        self.assertEqual(response.status_code, 201, response.content)
        quote = JobQuotation.objects.get(pk=response.json()['id'])
        sent = self.post(reverse('maintenance_quote_action', args=[self.job.pk, quote.pk, 'send']), {'version': quote.version})
        self.assertEqual(sent.status_code, 200, sent.content)
        quote.refresh_from_db()
        return quote

    def decision(self, quote, status='approved', key=None):
        self.client.force_login(self.pm)
        return self.post(reverse('maintenance_quote_decision', args=[self.job.pk, quote.pk]),
            {'status': status, 'reason': 'Please revise scope.' if status == 'rejected' else 'Approved scope.', 'version': quote.version}, key)

    def status(self, status, version):
        self.client.force_login(self.pm)
        return self.client.patch(self.detail_url, json.dumps({'status': status, 'version': version}), content_type='application/json')

    def test_new_job_creates_exactly_one_durable_operations_notification(self):
        with patch('portal.notifications.get_connection', side_effect=AssertionError('Must not send during job save')):
            job = self.new_job()
        event = JobActivity.objects.get()
        self.assertEqual(event.kind, 'job_submitted')
        self.assertEqual(event.actor, self.tenant)
        delivery = OperationsNotification.objects.get()
        self.assertEqual(delivery.event, event)
        self.assertEqual(delivery.recipient, 'maintenance@sevlink.co.za')
        self.assertEqual(delivery.state, 'pending')
        self.assertEqual(deliver(), 1)
        self.assertEqual(mail.outbox[0].to, ['maintenance@sevlink.co.za'])
        self.assertIn(str(job.pk), mail.outbox[0].body)
        self.assertIn('job='+str(job.pk), mail.outbox[0].body)
        self.assertNotIn('token=', mail.outbox[0].body)

    def test_submission_replay_with_key_is_not_a_new_job_or_email(self):
        key = uuid.uuid4()
        self.new_job(key)
        response = self.post(self.collection, {'property': str(self.home.pk), 'title': 'Kitchen repair',
            'description': 'Private tenant description', 'category': 'Plumbing'}, key)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(MaintenanceRequest.objects.count(), 1)
        self.assertEqual(OperationsNotification.objects.count(), 1)
        changed = self.post(self.collection, {'property': str(self.home.pk), 'title': 'Changed',
            'description': 'Private tenant description', 'category': 'Plumbing'}, key)
        self.assertEqual(changed.status_code, 409)

    def test_tenant_and_pm_comments_are_real_and_notify_once_each(self):
        self.new_job()
        for user in [self.tenant, self.pm]:
            self.client.force_login(user)
            key = uuid.uuid4()
            response = self.post(self.comment_url, {'text': 'Please arrange access.'}, key)
            self.assertEqual(response.status_code, 201)
            self.assertEqual(self.post(self.comment_url, {'text': 'Please arrange access.'}, key).status_code, 200)
            self.assertEqual(self.post(self.comment_url, {'text': 'Different'}, key).status_code, 409)
        self.assertEqual(JobComment.objects.count(), 2)
        self.assertEqual(OperationsNotification.objects.filter(event__kind='comment_added').count(), 2)
        data = self.client.get(self.detail_url).json()
        self.assertEqual(len(data['comments']), 2)
        self.assertEqual([e['actor'] for e in data['activity'][-2:]], [self.tenant.first_name, self.pm.first_name])
        self.assertTrue(all(e['at'] for e in data['activity']))

    def test_admin_comments_notify_but_operations_own_comments_do_not_loop(self):
        self.new_job()
        for user in [self.admin, self.ops]:
            self.client.force_login(user)
            self.assertEqual(self.post(self.comment_url, {'text': 'Shared follow-up.'}).status_code, 201)
        self.assertEqual(JobComment.objects.count(), 2)
        self.assertEqual(OperationsNotification.objects.filter(event__kind='comment_added').count(), 1)
        self.client.force_login(self.tenant)
        body = str(self.client.get(self.detail_url).json())
        self.assertNotIn('PRIVATE-STAFF-NAME', body)
        self.assertIn('Sevlink Operations', body)
        self.ops.is_superuser = False; self.ops.save()
        self.assertNotIn('PRIVATE-STAFF-NAME', str(self.client.get(self.detail_url).json()))

    def test_approval_and_rejection_each_notify_once_and_cannot_be_changed(self):
        self.new_job()
        for decision in ['approved', 'rejected']:
            quote = self.new_quote()
            key = uuid.uuid4()
            response = self.decision(quote, decision, key)
            self.assertEqual(response.status_code, 200, response.content)
            self.assertEqual(self.decision(quote, decision, key).status_code, 200)
            self.assertEqual(self.decision(quote, decision).status_code, 409)
            quote.refresh_from_db()
            self.assertEqual(quote.status, decision)
            self.assertEqual(quote.decided_by, self.pm)
        self.assertEqual(OperationsNotification.objects.filter(event__kind__in=['quote_approved','quote_rejected']).count(), 2)
        self.assertEqual(JobActivity.objects.filter(kind='quote_created').count(), 2)

    def test_quote_issue_replay_and_financial_data_are_scoped(self):
        self.new_job()
        key = uuid.uuid4()
        self.new_quote(key)
        replay = self.upload_quote(key)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(JobQuotation.objects.count(), 1)
        self.assertEqual(OperationsNotification.objects.count(), 1)
        self.client.force_login(self.tenant)
        data = self.client.get(self.detail_url).json()
        self.assertEqual(data['quotations'], [])
        self.assertFalse(any(e['type'].startswith('quote_') for e in data['activity']))
        self.assertNotIn('1250.50', str(data))
        self.assertEqual(self.post(self.quote_url, {'title':'Forged','scope':'Test','amount':'100'}).status_code, 403)

    def test_cross_agency_cotenant_and_unassigned_pm_cannot_comment_or_decide(self):
        self.new_job()
        quote = self.new_quote()
        for user in [self.foreign, self.cotenant, self.other_pm]:
            self.client.force_login(user)
            self.assertEqual(self.post(self.comment_url, {'text':'Not authorized'}).status_code, 404)
            self.assertEqual(self.post(reverse('maintenance_quote_decision',args=[self.job.pk,quote.pk]),
                {'status':'approved','reason':'Approved scope.','version':quote.version}).status_code, 404)
        self.assertEqual(JobComment.objects.count(), 0)
        self.assertEqual(OperationsNotification.objects.count(), 1)

    def test_tenant_and_operations_cannot_approve_agency_quotations(self):
        self.new_job(); quote = self.new_quote()
        for user in [self.tenant, self.ops]:
            self.client.force_login(user)
            self.assertEqual(self.post(reverse('maintenance_quote_decision',args=[self.job.pk,quote.pk]),
                {'status':'approved','reason':'Approved scope.','version':quote.version}).status_code, 403)
        self.client.force_login(self.admin)
        response = self.post(reverse('maintenance_quote_decision',args=[self.job.pk,quote.pk]),
            {'status':'approved','reason':'Approved scope.','version':quote.version})
        self.assertEqual(response.status_code, 200)

    def test_cancellation_completion_and_all_status_changes_are_recorded(self):
        self.new_job()
        self.assertEqual(self.status('reviewed',1).status_code,200)
        self.assertEqual(self.status('in_progress',2).status_code,200)
        self.assertEqual(self.status('completed',3).status_code,200)
        self.assertEqual(self.status('completed',3).status_code,409)
        self.assertEqual(OperationsNotification.objects.filter(event__kind='job_completed').count(),1)
        self.assertEqual(JobActivity.objects.filter(request=self.job).count(),4)
        self.new_job()
        self.assertEqual(self.status('cancelled',1).status_code,200)
        self.assertEqual(OperationsNotification.objects.filter(event__kind='job_cancelled').count(),1)
        self.assertEqual(OperationsNotification.objects.count(),4)  # two submissions, completion, cancellation

    def test_failed_and_invalid_mutations_do_not_create_events_or_outbox(self):
        self.new_job()
        with patch('portal.collaboration.Audit.objects.create', side_effect=RuntimeError('rollback')):
            with self.assertRaises(RuntimeError):
                self.post(self.comment_url, {'text':'This must roll back.'})
        self.assertEqual(JobComment.objects.count(),0)
        self.assertEqual(JobActivity.objects.count(),1)
        self.assertEqual(OperationsNotification.objects.count(),1)
        self.assertEqual(self.post(self.comment_url, {'text':''}).status_code,400)
        self.assertEqual(self.post(self.comment_url, {'text':'x'*2501}).status_code,400)
        self.assertEqual(self.post(self.comment_url, {'text':'x','author':'forged'}).status_code,400)
        self.assertEqual(self.client.post(self.comment_url, '{"text":"x"}',content_type='application/json').status_code,400)

    def test_invalid_quotes_decisions_closed_jobs_and_foreign_quote_ids(self):
        self.new_job(); quote = self.new_quote()
        for amount in ['0','-10','NaN','1.001']:
            self.assertEqual(self.post(self.quote_url,{'title':'Test','scope':'Test','amount':amount}).status_code,400)
        self.client.force_login(self.pm)
        url = reverse('maintenance_quote_decision',args=[self.job.pk,quote.pk])
        for body in [{'status':'rejected','reason':'','version':1}, {'status':'approved','version':True},
                     {'status':'approved','version':'1'}, {'status':'pending','version':1}]:
            self.assertEqual(self.post(url,body).status_code,400)
        self.assertEqual(self.post(reverse('maintenance_quote_decision',args=[self.job.pk,uuid.uuid4()]),
            {'status':'approved','reason':'Approved scope.','version':quote.version}).status_code,404)
        self.assertEqual(self.status('cancelled',1).status_code,200)
        self.assertEqual(self.post(url,{'status':'approved','reason':'Approved scope.','version':quote.version}).status_code,409)
        self.client.force_login(self.ops)
        self.assertEqual(self.post(self.quote_url,{'title':'Test','scope':'Test','amount':'10'}).status_code,400)

    def test_messages_contain_required_context_without_private_payloads(self):
        self.new_job()
        MaintenanceRequest.objects.filter(pk=self.job.pk).update(internal_notes='PRIVATE SUBCONTRACTOR COST')
        self.post(self.comment_url,{'text':'SENSITIVE COMMENT BODY and tenant@example.test'})
        quote = self.new_quote(); self.decision(quote)
        deliver()
        self.assertEqual(len(mail.outbox),3)
        for message in mail.outbox:
            self.assertEqual(message.to,['maintenance@sevlink.co.za'])
            self.assertFalse(message.cc or message.bcc)
            for value in ['Job: SV-', 'Property: Event Home', 'Agency: Event Agency A', 'Timestamp:', 'Event:', 'Details:', '/maintenance/?job=']:
                self.assertIn(value,message.body)
            for private in ['PRIVATE SUBCONTRACTOR','PRIVATE ACCESS CODE','PRIVATE PHONE','tenant@example.test','SENSITIVE COMMENT BODY','Private tenant description']:
                self.assertNotIn(private,message.body)

    @override_settings(OPERATIONS_NOTIFICATION_EMAIL='ops-review@example.test', SITE_URL='https://portal.example.test')
    def test_configurable_recipient_and_trusted_secure_link(self):
        self.new_job()
        event = JobActivity.objects.get(); event.property_name = 'Event Home\nEvent: forged'
        _, preview = notification_message(event)
        self.assertEqual(preview.count('\nEvent:'), 1)
        self.assertIn('Property: Event Home Event: forged', preview)
        deliver()
        self.assertEqual(mail.outbox[0].to,['ops-review@example.test'])
        self.assertIn('https://portal.example.test/maintenance/?job=',mail.outbox[0].body)
        self.assertNotIn('testserver',mail.outbox[0].body)

    def test_csrf_and_method_restrictions(self):
        self.new_job(); quote = self.new_quote()
        strict = Client(enforce_csrf_checks=True); strict.force_login(self.pm)
        self.assertEqual(strict.post(self.comment_url,'{"text":"hello"}',content_type='application/json',HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())).status_code,403)
        strict.get(reverse('maintenance_context'))
        self.assertEqual(strict.post(self.comment_url,'{"text":"hello"}',content_type='application/json',
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),HTTP_X_CSRFTOKEN=strict.cookies['csrftoken'].value).status_code,201)
        self.assertEqual(self.client.get(self.comment_url).status_code,405)
        self.assertEqual(self.client.get(self.quote_url).status_code,405)
        self.assertEqual(self.client.get(reverse('maintenance_quote_decision',args=[self.job.pk,quote.pk])).status_code,405)

    def test_event_interface_deduplicates_and_rejects_private_fields(self):
        job=self.new_job(); event=JobActivity.objects.get()
        with transaction.atomic():
            same=record(job,self.tenant,'job_submitted',event.dedup_key,{'status':job.status})
        self.assertEqual(same.pk,event.pk)
        self.assertEqual(OperationsNotification.objects.count(),1)
        with self.assertRaises(ValueError), transaction.atomic():
            record(job,self.tenant,'job_submitted','invalid',{'status':job.status,'internal_notes':'private'})

    def test_delivery_retries_backoff_and_final_audit_without_resending_success(self):
        self.new_job()
        with patch('portal.notifications.get_connection',side_effect=OSError('SECRET SMTP ERROR')):
            self.assertEqual(deliver(),1)
        notification=OperationsNotification.objects.get()
        self.assertEqual((notification.state,notification.attempts,notification.error_code),('pending',1,'delivery_failed'))
        self.assertGreater(notification.next_attempt_at,timezone.now())
        self.assertEqual(deliver(),0)
        self.assertNotIn('SECRET',str(OperationsDeliveryAttempt.objects.values().get()))
        OperationsNotification.objects.update(next_attempt_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(deliver(),1)
        self.assertEqual(deliver(),0)
        notification.refresh_from_db()
        self.assertEqual(notification.state,'sent')
        self.assertEqual(list(notification.delivery_attempts.values_list('outcome',flat=True)),['failed','sent'])
        self.assertEqual(len(mail.outbox),1)
        self.assertIn(str(notification.event_id),mail.outbox[0].extra_headers['Message-ID'])

    def test_retry_exhaustion_and_stale_worker_recovery_are_audited(self):
        self.new_job()
        lease=claim()
        self.assertIsNone(claim())
        OperationsNotification.objects.update(lease_expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(deliver(),1)
        self.assertEqual(OperationsDeliveryAttempt.objects.get(number=1).outcome,'uncertain')
        self.assertEqual(OperationsNotification.objects.get().state,'sent')
        self.new_job()
        with patch('portal.notifications.get_connection',side_effect=OSError('unavailable')):
            for _ in range(5):
                OperationsNotification.objects.filter(state='pending').update(next_attempt_at=timezone.now()-timedelta(seconds=1))
                deliver()
        failed=OperationsNotification.objects.get(state='dead')
        self.assertEqual(failed.attempts,5)
        self.assertEqual(failed.delivery_attempts.count(),5)
        self.assertEqual(deliver(),0)

    def test_live_backend_is_disabled_and_queue_backend_loop_is_rejected(self):
        self.new_job()
        with self.settings(OPERATIONS_EMAIL_DELIVERY_BACKEND='django.core.mail.backends.smtp.EmailBackend'):
            with self.assertRaises(ImproperlyConfigured): deliver()
        with self.settings(OPERATIONS_EMAIL_DELIVERY_BACKEND='portal.mail.QueueBackend', OPERATIONS_LIVE_DELIVERY_ENABLED=True):
            with self.assertRaises(ImproperlyConfigured): deliver()
        self.assertEqual(OperationsNotification.objects.get().attempts,0)

    def test_local_preview_backend_and_configuration_checks(self):
        self.new_job()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'preview'
            with self.settings(OPERATIONS_EMAIL_DELIVERY_BACKEND='portal.mail.PrivatePreviewBackend',EMAIL_FILE_PATH=root):
                call_command('send_operations_notifications',stdout=io.StringIO())
            files=list(root.iterdir())
            self.assertEqual(len(files),1)
            self.assertIn('maintenance@sevlink.co.za',files[0].read_text())
            if __import__('os').name!='nt': self.assertEqual(files[0].stat().st_mode & 0o777,0o600)
        with self.settings(OPERATIONS_NOTIFICATION_EMAIL='invalid\nBcc:evil@example.test'):
            self.assertEqual(operations_configuration(None)[0].id,'portal.E002')
        with self.settings(SITE_URL='https://user:password@example.test'):
            self.assertEqual(operations_configuration(None)[0].id,'portal.E003')


@override_settings(OPERATIONS_EMAIL_DELIVERY_BACKEND=LOCAL, OPERATIONS_LIVE_DELIVERY_ENABLED=False)
class DeliveryTransactionTests(TransactionTestCase):
    def test_delivery_runs_outside_job_transaction_and_failure_cannot_rollback_job(self):
        user=User.objects.create_user(username='transaction@example.test',email='transaction@example.test')
        agency=Agency.objects.create(name='Transaction agency',phone='test',area='Test')
        Membership.objects.create(user=user,agency=agency,role='tenant')
        prop=Property.objects.create(agency=agency,name='Home',address='Example')
        with transaction.atomic():
            job=MaintenanceRequest.objects.create(property=prop,reported_by=user,title='Repair',description='Test',category='Plumbing')
            record(job,user,'job_submitted','transaction-test',{'status':job.status})
        def unavailable(*args,**kwargs):
            self.assertFalse(connection.in_atomic_block)
            raise OSError('provider unavailable')
        with patch('portal.notifications.get_connection',side_effect=unavailable): deliver()
        self.assertTrue(MaintenanceRequest.objects.filter(pk=job.pk).exists())
        self.assertEqual(OperationsNotification.objects.get().state,'pending')
        with self.assertRaises(RuntimeError):
            record(job,user,'job_submitted','outside-transaction',{'status':job.status})
