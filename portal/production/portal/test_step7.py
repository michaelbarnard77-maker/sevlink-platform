"""Quotation revision, private conversation and Operations inbox security contracts."""
import io
import json
import tempfile
import uuid
from contextlib import contextmanager
from django.conf import settings
from decimal import Decimal
from unittest.mock import patch
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse
from PIL import Image
from . import test_notifications as fixtures
from .models import (JobQuotation, QuotationLine, QuotationAction, JobActivity, JobComment,
                     OperationsInboxItem, OperationsInboxReceipt, OperationsNotification, MaintenanceAttachment,
                     User, Agency, Property, MaintenanceRequest, Membership)
from .notifications import deliver
from .quotations import content


@contextmanager
def private_storage(directory):
    aliases = {**settings.STORAGES, 'maintenance_private': {
        'BACKEND': 'portal.attachment_storage.PrivateAttachmentStorage', 'OPTIONS': {'location': directory}}}
    with override_settings(PRIVATE_ATTACHMENT_ROOT=directory, STORAGES=aliases):
        yield


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False,
                   ALLOWED_HOSTS=['testserver'], OPERATIONS_EMAIL_DELIVERY_BACKEND=fixtures.LOCAL,
                   OPERATIONS_LIVE_DELIVERY_ENABLED=False, SEVLINK_VAT_RATE='0.125')
class Step7Tests(TestCase):
    setUpTestData = classmethod(fixtures.EventWorkflowTests.setUpTestData.__func__)
    post = fixtures.EventWorkflowTests.post
    new_job = fixtures.EventWorkflowTests.new_job

    def setUp(self):
        self.new_job()
        self.client.force_login(self.ops)

    def draft(self, **changes):
        data = dict(title='Public repair scope', scope='Agency-visible work.', tax_treatment='exclusive',
            lines=[dict(description='Tap replacement', quantity='2.5', unit='hour', unit_price='100.05')],
            internal=dict(cost_total='100', commission_total='25', notes='PRIVATE SUBCONTRACTOR IDENTITY'))
        data.update(changes)
        response = self.post(self.quote_url, data)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def mutate(self, quote, operation, **values):
        return self.post(reverse('maintenance_quote_action', args=[self.job.pk, quote['id'], operation]),
                         dict(version=quote['version'], **values))

    def sent(self):
        quote = self.draft()
        response = self.mutate(quote, 'send')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def decide(self, quote, status='approved'):
        self.client.force_login(self.pm)
        return self.mutate(quote, 'decision', status=status, reason='Decision audit comment.')

    def detail(self, user):
        self.client.force_login(user)
        return self.client.get(self.detail_url).json()

    def test_decimal_exclusive_inclusive_and_no_vat_rounding(self):
        quote = self.draft()
        self.assertEqual(Decimal(quote['subtotal']), Decimal('250.13'))
        self.assertEqual(Decimal(quote['vat_total']), Decimal('31.27'))
        self.assertEqual(Decimal(quote['amount']), Decimal('281.40'))
        for treatment, expected in [('inclusive', ('222.34', '27.79', '250.13')), ('none', ('250.13', '0.00', '250.13'))]:
            data = self.draft(tax_treatment=treatment)
            self.assertEqual(tuple(Decimal(data[k]) for k in ('subtotal','vat_total','amount')), tuple(map(Decimal, expected)))
        self.assertEqual(QuotationLine.objects.count(), 3)

    @override_settings(SEVLINK_VAT_RATE='')
    def test_taxable_quotes_require_configuration(self):
        response = self.post(self.quote_url, dict(title='VAT', amount='100', tax_treatment='exclusive'))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(JobQuotation.objects.count(), 0)
        self.assertEqual(Decimal(self.draft(tax_treatment='none')['vat_rate']), Decimal(0))

    def test_reject_invalid_quantities_precision_rate_and_currency_overflow(self):
        for qty, price in [('0','10'), ('1.0001','10'), ('1','1.001'), ('NaN','1'), ('1',True), ('999999999.999','9999999999.99')]:
            response = self.post(self.quote_url, {'title':'Invalid','lines':[dict(description='Work',quantity=qty,unit='job',unit_price=price)]})
            self.assertEqual(response.status_code,400,response.content)
        for rate in ('bad', '-0.01', '1.1', '0.1234567'):
            with override_settings(SEVLINK_VAT_RATE=rate):
                self.assertEqual(self.post(self.quote_url,dict(title='Test',amount='10',tax_treatment='exclusive')).status_code,400)
        self.assertEqual(JobQuotation.objects.count(),0)

    def test_drafts_hidden_and_internal_money_never_in_external_response(self):
        quote = self.draft()
        self.assertEqual(self.detail(self.pm)['quotations'], [])
        self.assertFalse(any(e['type'].startswith('quote_') for e in self.detail(self.pm)['activity']))
        self.client.force_login(self.ops)
        quote = self.mutate(quote,'send').json()
        for user in (self.pm,self.admin):
            data = self.detail(user)
            self.assertEqual(len(data['quotations']),1)
            encoded = json.dumps(data)
            for secret in ('PRIVATE SUBCONTRACTOR','cost_total','commission_total','private_details','internal'):
                self.assertNotIn(secret,encoded)
        self.assertEqual(self.detail(self.tenant)['quotations'],[])
        self.assertEqual(self.detail(self.ops)['quotations'][0]['internal']['notes'],'PRIVATE SUBCONTRACTOR IDENTITY')

    def test_edit_requires_version_draft_and_idempotency(self):
        quote = self.draft()
        edited = self.mutate(quote,'edit', title='Revised draft',amount='500',tax_treatment='none')
        self.assertEqual(edited.status_code,200)
        self.assertEqual(edited.json()['amount'],'500.00')
        self.assertEqual(self.mutate(quote,'edit',title='Stale',amount='20').status_code,409)
        quote = edited.json()
        quote = self.mutate(quote,'send').json()
        self.assertEqual(self.mutate(quote,'edit',title='Tamper',amount='20').status_code,409)
        self.client.force_login(self.pm)
        self.assertEqual(self.mutate(quote,'edit',title='Tamper',amount='20').status_code,403)

    def test_saved_vat_snapshot_approval_and_approved_model_immutability(self):
        quote = self.sent()
        with override_settings(SEVLINK_VAT_RATE='0.2'):
            response = self.decide(quote)
        self.assertEqual(response.status_code,200,response.content)
        approved = JobQuotation.objects.get(pk=quote['id'])
        self.assertEqual(approved.vat_rate,Decimal('.125'))
        self.assertEqual(approved.public_snapshot['amount'],'281.40')
        approved.amount = Decimal('1')
        with self.assertRaises(ValidationError):
            approved.save()
        line = approved.lines.get()
        line.unit_price = Decimal('1')
        with self.assertRaises(ValidationError):
            line.save()
        with self.assertRaises(ValidationError):
            line.delete()
        self.client.force_login(self.ops)
        self.assertEqual(self.mutate(response.json(),'revise').status_code,409)
        self.assertEqual(self.mutate(response.json(),'send').status_code,409)
        self.assertEqual(QuotationAction.objects.filter(quote_id=quote['id']).count(),3)

    def test_revision_request_supersedes_and_stale_approval_fails(self):
        old = self.sent()
        decision = self.decide(old,'revision_requested')
        self.assertEqual(decision.status_code,200,decision.content)
        self.assertEqual(OperationsNotification.objects.filter(event__kind='quote_revision_requested').count(),1)
        self.client.force_login(self.ops)
        revised = self.mutate(decision.json(),'revise')
        self.assertEqual(revised.status_code,201,revised.content)
        new = revised.json()
        self.assertEqual((new['revision'],new['series_id'],new['status']),(2,old['series_id'],'draft'))
        self.assertEqual(new['amount'],old['amount'])
        self.assertEqual(JobQuotation.objects.get(pk=old['id']).status,'superseded')
        self.assertEqual(self.decide(old).status_code,409)
        self.client.force_login(self.ops)
        new = self.mutate(new,'send').json()
        self.assertEqual(self.decide(new).status_code,200)
        self.assertEqual(QuotationAction.objects.filter(kind='approved').count(),1)

    def test_decision_comments_replays_and_stale_versions(self):
        quote = self.sent()
        self.client.force_login(self.pm)
        self.assertEqual(self.mutate(quote,'decision',status='approved',reason='').status_code,400)
        stale = dict(quote,version=quote['version']-1)
        self.assertEqual(self.mutate(stale,'decision',status='approved',reason='OK').status_code,409)
        url = reverse('maintenance_quote_decision',args=[self.job.pk,quote['id']])
        key = uuid.uuid4(); body = dict(version=quote['version'],status='approved',reason='OK')
        self.assertEqual(self.post(url,body,key).status_code,200)
        self.assertEqual(self.post(url,body,key).status_code,200)
        self.assertEqual(self.post(url,dict(body,status='rejected'),key).status_code,409)
        self.assertEqual(self.post(url,body).status_code,409)
        self.assertEqual(OperationsInboxItem.objects.filter(event__kind='quote_approved').count(),1)

    def test_quote_pdf_and_cross_agency_document_isolation(self):
        quote = self.draft()
        url = reverse('maintenance_quote_pdf',args=[self.job.pk,quote['id']])
        self.client.force_login(self.pm)
        self.assertEqual(self.client.get(url).status_code,404)
        self.client.force_login(self.ops)
        self.mutate(quote,'send')
        for user, status in [(self.pm,200),(self.admin,200),(self.ops,200),(self.tenant,403),(self.foreign,404),(self.other_pm,404),(self.cotenant,404)]:
            self.client.force_login(user)
            response = self.client.get(url)
            self.assertEqual(response.status_code,status,response.content[:100])
            if status == 200:
                self.assertTrue(response.content.startswith(b'%PDF-'))
                self.assertIn('no-store',response['Cache-Control'])
        # The PDF generator obtains only the public serializer; private records are never accessed.
        self.client.force_login(self.pm)
        with patch('portal.quotations.QuotationPrivate.objects.filter',side_effect=AssertionError('Private data in public PDF')):
            self.assertEqual(self.client.get(url).status_code,200)
        for operation in ('send','edit','revise','decision'):
            self.client.force_login(self.foreign)
            self.assertEqual(self.mutate(quote,operation,status='approved',reason='OK').status_code,404)

    def photo(self):
        output = io.BytesIO(); Image.new('RGB',(8,8),'orange').save(output,format='PNG')
        return SimpleUploadedFile('private-photo.png',output.getvalue(),content_type='image/png')

    def test_internal_comment_and_files_hidden_in_list_detail_and_direct_download(self):
        with tempfile.TemporaryDirectory() as directory, private_storage(directory):
            key = uuid.uuid4()
            response = self.client.post(self.comment_url,{'text':'PRIVATE SUBCONTRACTOR IDENTITY','visibility':'internal','attachments':self.photo()},HTTP_IDEMPOTENCY_KEY=str(key))
            self.assertEqual(response.status_code,201,response.content)
            file = response.json()['attachments'][0]
            self.assertEqual(OperationsNotification.objects.count(),1)  # submission only
            for user in (self.pm,self.admin,self.tenant):
                data = self.detail(user)
                self.assertEqual(data['comments'],[])
                self.assertEqual(data['attachments'],[])
                self.assertNotIn('PRIVATE SUBCONTRACTOR',json.dumps(data))
                self.assertNotIn('PRIVATE SUBCONTRACTOR',self.client.get(self.collection).content.decode())
                self.assertEqual(self.client.get(file['download_url']).status_code,404)
                self.assertEqual(self.post(self.comment_url,{'text':'Forged','visibility':'internal'}).status_code,403)
            self.detail(self.ops)
            result=self.client.get(file['download_url'])
            self.assertEqual(result.status_code,200); b''.join(result.streaming_content)
            self.assertEqual(len(self.detail(self.ops)['comments']),1)
            self.assertEqual(MaintenanceAttachment.objects.get().comment_id,JobComment.objects.get().pk)

    def test_shared_comment_files_and_disabled_tenant_conversation(self):
        with tempfile.TemporaryDirectory() as directory, private_storage(directory):
            self.client.force_login(self.pm)
            response=self.client.post(self.comment_url,{'text':'Shared file','attachments':self.photo()},HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
            self.assertEqual(response.status_code,201,response.content)
            url=response.json()['attachments'][0]['download_url']
            self.client.force_login(self.tenant)
            result=self.client.get(url);self.assertEqual(result.status_code,200);b''.join(result.streaming_content)
            self.client.force_login(self.foreign)
            self.assertEqual(self.client.get(url).status_code,404)
            self.assertEqual(self.post(self.comment_url,{'text':'Foreign'}).status_code,404)
            permission=reverse('maintenance_conversation_permissions',args=[self.job.pk])
            self.client.force_login(self.pm)
            self.assertEqual(self.post(permission,{'version':1,'tenant_comments_allowed':False}).status_code,403)
            self.client.force_login(self.ops)
            self.assertEqual(self.post(permission,{'version':1,'tenant_comments_allowed':False}).status_code,200)
            data=self.detail(self.tenant)
            self.assertEqual(data['comments'],[]);self.assertEqual(data['attachments'],[])
            self.assertFalse(data['tenant_comments_allowed'])
            self.assertEqual(self.client.get(url).status_code,404)
            self.assertEqual(self.post(self.comment_url,{'text':'Disabled'}).status_code,403)
            self.assertFalse(any(e['type']=='comment_added' for e in data['activity']))
            self.assertEqual(len(self.detail(self.pm)['comments']),1)

    def test_comment_attachment_rollback_invalid_and_idempotent_uploads(self):
        with tempfile.TemporaryDirectory() as directory, private_storage(directory):
            self.client.force_login(self.pm)
            key=uuid.uuid4()
            def post():
                return self.client.post(self.comment_url,{'text':'Photo','attachments':self.photo()},HTTP_IDEMPOTENCY_KEY=str(key))
            self.assertEqual(post().status_code,201)
            self.assertEqual(post().status_code,200)
            self.assertEqual(MaintenanceAttachment.objects.count(),1)
            bad=SimpleUploadedFile('bad.html',b'<script>alert(1)</script>',content_type='text/html')
            self.assertEqual(self.client.post(self.comment_url,{'text':'Bad','attachments':bad},HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())).status_code,400)
            with patch('portal.collaboration.record',side_effect=RuntimeError('rollback')):
                with self.assertRaises(RuntimeError):
                    self.client.post(self.comment_url,{'text':'Rollback','attachments':self.photo()},HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
            self.assertEqual(JobComment.objects.count(),1)
            self.assertEqual(MaintenanceAttachment.objects.count(),1)
            from pathlib import Path
            self.assertEqual(len([p for p in Path(directory).rglob('*') if p.is_file()]),1)

    def test_notification_centre_persistent_per_operator_private_and_independent_of_email(self):
        url=reverse('operations_notifications')
        notice=OperationsInboxItem.objects.get()
        state=reverse('operations_notification_state',args=[notice.pk])
        for user in (self.pm,self.admin,self.tenant,self.foreign):
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code,403)
            self.assertEqual(self.post(state,{'read':True}).status_code,403)
        self.client.force_login(self.ops)
        data=self.client.get(url).json()
        self.assertEqual((data['unread_count'],len(data['items'])),(1,1))
        self.assertEqual(data['items'][0]['agency'],self.agency.name)
        version,status=self.job.version,self.job.status
        self.assertEqual(self.post(state,{'read':True}).status_code,200)
        self.assertEqual(self.post(state,{'read':True}).status_code,200)
        self.assertEqual(JobActivity.objects.filter(kind='notification_state').count(),1)
        self.client.logout();self.client.force_login(self.ops)
        self.assertEqual(self.client.get(url).json()['unread_count'],0)
        self.job.refresh_from_db();self.assertEqual((self.job.version,self.job.status),(version,status))
        self.assertEqual(OperationsNotification.objects.get().state,'pending')
        second=User.objects.create_user(username='second-ops@example.test',email='second-ops@example.test',is_superuser=True,is_staff=True)
        self.client.force_login(second)
        self.assertEqual(self.client.get(url).json()['unread_count'],1)
        self.client.force_login(self.ops)
        self.assertEqual(self.post(state,{'read':False}).status_code,200)
        self.assertEqual(self.client.get(url).json()['unread_count'],1)
        with patch('portal.notifications.get_connection',side_effect=OSError('offline')):
            deliver()
        self.assertEqual(self.client.get(url).json()['unread_count'],1)
        self.assertEqual(OperationsInboxItem.objects.count(),1)
        self.assertFalse(any(e['type']=='notification_state' for e in self.detail(self.pm)['activity']))

    def test_notification_pagination_csrf_and_strict_receipt_state(self):
        from datetime import timedelta
        from django.test import Client
        from django.utils import timezone
        from .events import record
        with transaction.atomic():
            for index in range(54):
                event = record(self.job, self.pm, 'comment_added', f'pagination-comment:{index}',
                    {'comment_id': str(uuid.uuid4()), 'text': 'Test shared comment'})
        feed = reverse('operations_notifications')
        self.client.force_login(self.ops)
        page = self.client.get(feed).json()
        self.assertEqual((len(page['items']),page['unread_count']),(50,55))
        older = self.client.get(feed+'?before='+str(page['next'])).json()
        self.assertEqual(len(older['items']),5)
        self.assertFalse({i['id'] for i in page['items']} & {i['id'] for i in older['items']})
        self.assertIsNone(older['next'])
        item_url=reverse('operations_notification_state',args=[page['items'][0]['id']])
        for value in ('true',1,None,[]):
            self.assertEqual(self.post(item_url,{'read':value}).status_code,400)
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.ops)
        self.assertEqual(strict.post(item_url,json.dumps({'read':True}),content_type='application/json').status_code,403)
        # Inbox retention does not depend on keeping its separate pending email row.
        OperationsNotification.objects.all().delete()
        self.assertEqual(self.client.get(feed).json()['unread_count'],55)

    def test_local_email_all_required_types_branded_safe_and_retry_audited(self):
        for decision in ('approved','rejected','revision_requested'):
            self.client.force_login(self.ops)
            self.assertEqual(self.decide(self.sent(),decision).status_code,200)
        self.client.force_login(self.tenant)
        self.assertEqual(self.post(self.comment_url,{'text':'PRIVATE tenant email@example.test'}).status_code,201)
        self.client.force_login(self.pm)
        self.client.patch(self.detail_url,json.dumps({'status':'cancelled','version':1}),content_type='application/json')
        self.new_job()
        self.client.force_login(self.pm)
        for version,status in enumerate(('reviewed','in_progress','completed'),1):
            self.assertEqual(self.client.patch(self.detail_url,json.dumps(dict(status=status,version=version)),content_type='application/json').status_code,200)
        self.assertEqual(deliver(),8)  # 2 submitted + three decisions + comment + cancelled + completed
        self.assertEqual(len(mail.outbox),8)
        for message in mail.outbox:
            self.assertIn('SEVLINK',message.alternatives[0].content)
            self.assertNotIn('PRIVATE',message.body)
            self.assertNotIn('PRIVATE',message.alternatives[0].content)
            self.assertEqual(message.to,['maintenance@sevlink.co.za'])
        self.assertEqual(OperationsInboxItem.objects.count(),8)
        self.assertEqual(OperationsNotification.objects.filter(state='sent').count(),8)
        self.assertEqual(deliver(),0)

    def test_audit_comments_and_decision_history_are_append_only(self):
        self.post(self.comment_url, {'text':'Immutable note','visibility':'internal'})
        quote = self.sent()
        self.decide(quote)
        for obj in (JobComment.objects.get(), JobActivity.objects.first(), QuotationAction.objects.first()):
            with self.assertRaises(ValidationError):
                obj.save()
            with self.assertRaises(ValidationError):
                obj.delete()
            with self.assertRaises(ValidationError):
                type(obj).objects.filter(pk=obj.pk).delete()
            with self.assertRaises(ValidationError):
                type(obj).objects.filter(pk=obj.pk).update(created_at=obj.created_at)
        # No editable activity/quote history endpoints exist for ordinary portal users.
        self.client.force_login(self.pm)
        self.assertEqual(self.client.delete(self.comment_url).status_code,405)
        inbox=reverse('operations_notifications')
        self.pm.is_staff=True;self.pm.save()
        self.assertEqual(self.client.get(inbox).status_code,403)

    def test_failures_roll_back_quote_action_and_do_not_create_notifications(self):
        quote=self.sent()
        self.client.force_login(self.pm)
        with patch('portal.quotations.record',side_effect=RuntimeError('rollback')):
            with self.assertRaises(RuntimeError):
                self.mutate(quote,'decision',status='approved',reason='OK')
        self.assertEqual(JobQuotation.objects.get(pk=quote['id']).status,'sent')
        self.assertFalse(QuotationAction.objects.filter(kind='approved').exists())
        self.assertEqual(OperationsInboxItem.objects.count(),1)


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver'])
class ConcurrentQuotationTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_simultaneous_approve_reject_has_one_winner_and_one_notification(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        from django.test import Client
        agency=Agency.objects.create(name='Concurrent agency',phone='test',area='test')
        pm=User.objects.create_user(username='race-pm@example.test',email='race-pm@example.test')
        Membership.objects.create(user=pm,agency=agency,role='pm')
        prop=Property.objects.create(agency=agency,manager=pm,name='Race home',address='Test')
        ops=User.objects.create_user(username='race-ops@example.test',email='race-ops@example.test',is_superuser=True)
        job=MaintenanceRequest.objects.create(property=prop,reported_by=pm,title='Race',description='Test',category='Plumbing')
        quote=JobQuotation.objects.create(request=job,created_by=ops,creation_key=uuid.uuid4(),title='Race quote',scope='Test',amount='100',status='sent')
        barrier=Barrier(2)
        def run(status):
            close_old_connections()
            try:
                client=Client();client.force_login(User.objects.get(pk=pm.pk));barrier.wait(timeout=15)
                return client.post(reverse('maintenance_quote_decision',args=[job.pk,quote.pk]),
                    json.dumps(dict(status=status,reason='Concurrent decision',version=1)),content_type='application/json',
                    HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())).status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results=list(executor.map(run,('approved','rejected')))
        self.assertEqual(sorted(results),[200,409])
        self.assertEqual(QuotationAction.objects.count(),1)
        self.assertEqual(OperationsNotification.objects.count(),1)
        self.assertEqual(OperationsInboxItem.objects.count(),1)
