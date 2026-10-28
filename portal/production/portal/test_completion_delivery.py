import io
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch
from email import policy
from email.parser import BytesParser
from django.test import TestCase,override_settings
from django.db import transaction
from django.urls import reverse
from pypdf import PdfReader
from . import test_operational_workflow as workflows
from .test_attachments import photo
from .models import CompletionPackage,CompletionRecord,MailQueue,MaintenanceRequest
from .completion_delivery import maybe_queue
from .account_mail import deliver


@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False,SMTP_DELIVERY_ENABLED=False,OPERATIONS_LIVE_DELIVERY_ENABLED=False)
class CompletionDeliveryTests(TestCase):
    setUpTestData=classmethod(workflows.OperationalWorkflowTests.setUpTestData.__func__)
    post=workflows.OperationalWorkflowTests.post
    act=workflows.OperationalWorkflowTests.act
    review=workflows.OperationalWorkflowTests.review
    invoice=workflows.OperationalWorkflowTests.invoice

    def setUp(self):
        workflows.OperationalWorkflowTests.setUp(self)
        self.home.manager=self.pm;self.home.save(update_fields=['manager'])
        self.review()
        self.url=reverse('completion_report_upload',args=[self.job.pk])

    def upload(self,key=None,after=True,mark_completed=False):
        self.client.force_login(self.ops);self.job.refresh_from_db()
        values={'version':self.job.version,'report':'Repair completed and tested.','mark_completed':str(mark_completed).lower(),'before_photos':photo(name='before.png')}
        if after:values['after_photos']=photo(name='after.png')
        return self.client.post(self.url,values,HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))

    def completed(self):
        r=self.upload();self.assertEqual(r.status_code,201,r.content)
        from .maintenance import update_status
        for status in ['attended','completed']:
            self.job.refresh_from_db();r=update_status(self.ops,self.job,{'status':status,'version':self.job.version});self.assertEqual(r.status_code,200,r.content)
        self.job.refresh_from_db()

    def package(self):
        self.completed();self.assertFalse(CompletionPackage.objects.exists())
        self.client.force_login(self.ops);r=self.invoice(purpose='final');self.assertEqual(r.status_code,201,r.content)
        return CompletionPackage.objects.get()

    def test_batch_groups_photos_and_missing_after_is_atomic(self):
        r=self.upload(after=False);self.assertEqual(r.status_code,400,r.content)
        self.assertFalse(self.job.attachments.filter(purpose='completion_before').exists())
        key=uuid.uuid4();r=self.upload(key);self.assertEqual(r.status_code,201,r.content)
        r=self.upload(key);self.assertEqual(r.status_code,200,r.content)
        self.assertEqual(CompletionRecord.objects.count(),1)
        self.assertEqual(set(self.job.attachments.values_list('purpose',flat=True)),{'completion_before','completion_after'})
        self.assertFalse(CompletionPackage.objects.exists())

    def test_report_and_invoice_are_two_attachments_in_one_private_preview(self):
        package=self.package();self.assertEqual(package.message.recipient,self.pm.email)
        with transaction.atomic():self.assertEqual(maybe_queue(self.job,self.ops).pk,package.pk)
        self.assertEqual(MailQueue.objects.count(),1)
        with tempfile.TemporaryDirectory() as directory,override_settings(EMAIL_FILE_PATH=Path(directory)):
            with patch('django.core.mail.backends.smtp.EmailBackend.send_messages') as smtp:
                self.assertEqual(deliver(preview=True),0);smtp.assert_not_called()
            logs=list(Path(directory).glob('*'));self.assertEqual(len(logs),1)
            message=BytesParser(policy=policy.default).parsebytes(logs[0].read_bytes())
            attachments=list(message.iter_attachments());self.assertEqual(len(attachments),2)
            self.assertTrue(all(a.get_content_type()=='application/pdf' for a in attachments))
            self.assertIn('completion-report.pdf',attachments[0].get_filename())
            reader=PdfReader(io.BytesIO(attachments[0].get_payload(decode=True)));self.assertGreaterEqual(len(reader.pages),2)
            self.assertIn(package.invoice.number,attachments[1].get_filename())
        package.message.refresh_from_db();self.assertIsNone(package.message.sent_at)
        self.assertEqual(package.message.error_code,'preview_only')

    def test_changed_pm_cannot_receive_old_package(self):
        package=self.package();self.home.manager=self.foreign;self.home.save(update_fields=['manager'])
        with tempfile.TemporaryDirectory() as directory,override_settings(EMAIL_FILE_PATH=Path(directory)):
            self.assertEqual(deliver(preview=True),0);self.assertEqual(list(Path(directory).glob('*')),[])
        package.message.refresh_from_db();self.assertIsNotNone(package.message.retired_at)
        self.assertEqual(package.message.error_code,'document_access_changed')

    def test_tenants_and_other_pms_cannot_prepare_or_inspect_delivery(self):
        package=self.package()
        for user in [self.pm,self.tenant,self.foreign]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse('completion_package_status',args=[self.job.pk])).status_code,404)
            self.assertEqual(self.client.post(self.url,{}).status_code,403)
        self.client.force_login(self.tenant)
        self.assertEqual(self.client.get(reverse('maintenance_attachment_download',args=[self.job.pk,package.report_document_id])).status_code,404)
        self.client.force_login(self.pm)
        self.assertEqual(self.client.get(reverse('maintenance_attachment_download',args=[self.job.pk,package.report_document_id])).status_code,200)

    def test_receipt_on_full_original_invoice_does_not_queue_before_work_complete(self):
        workflows.OperationalWorkflowTests.setUp(self)
        self.home.manager=self.pm;self.home.save(update_fields=['manager'])
        self.url=reverse('completion_report_upload',args=[self.job.pk])
        self.review('quoted');self.client.force_login(self.ops)
        quote=workflows.OperationalWorkflowTests.quote(self).json()
        sent=self.post(reverse('maintenance_quote_action',args=[self.job.pk,quote['id'],'send']),{'version':quote['version']}).json()
        self.client.force_login(self.pm)
        self.assertEqual(self.post(reverse('maintenance_quote_decision',args=[self.job.pk,quote['id']]),{'version':sent['version'],'status':'approved','reason':'Approved test work'}).status_code,200)
        self.client.force_login(self.ops);invoice=self.invoice(purpose='deposit').json()
        self.assertFalse(CompletionPackage.objects.exists())
        self.assertEqual(workflows.OperationalWorkflowTests.payment(self,invoice,amount='500').status_code,201)
        self.assertEqual(self.act('verify-deposit',user=self.ops,confirmation='VERIFY').status_code,200)
        self.completed()
        package=CompletionPackage.objects.get();self.assertEqual(str(package.invoice_id),invoice['id'])
        self.assertEqual(package.invoice.amount,1000)

    def test_package_is_blocked_if_invoice_is_voided(self):
        package=self.package()
        from .models import JobInvoice
        JobInvoice.objects.filter(pk=package.invoice_id).update(document_status='void')
        with tempfile.TemporaryDirectory() as directory,override_settings(EMAIL_FILE_PATH=Path(directory)):
            self.assertEqual(deliver(preview=True),0);self.assertEqual(list(Path(directory).glob('*')),[])
        package.message.refresh_from_db();self.assertEqual(package.message.error_code,'document_access_changed')

    def test_suppressed_pm_does_not_receive_the_package(self):
        package=self.package()
        from django.utils import timezone
        from .models import OperationsNotification,OperationsFeedback
        notification=OperationsNotification.objects.first();notification.recipient=self.pm.email;notification.save(update_fields=['recipient'])
        OperationsFeedback.objects.create(notification=notification,provider_event_id='synthetic-pm-bounce',kind='bounce',occurred_at=timezone.now())
        with tempfile.TemporaryDirectory() as directory,override_settings(EMAIL_FILE_PATH=Path(directory)):
            self.assertEqual(deliver(preview=True),0);self.assertEqual(list(Path(directory).glob('*')),[])
        package.message.refresh_from_db();self.assertEqual(package.message.error_code,'document_access_changed')

    def test_mark_completed_respects_the_existing_progress_gate(self):
        r=self.upload(mark_completed=True);self.assertEqual(r.status_code,400,r.content)
        self.assertFalse(CompletionRecord.objects.exists())
        self.assertFalse(self.job.attachments.filter(purpose='completion_before').exists())
        from .maintenance import update_status
        self.job.refresh_from_db();r=update_status(self.ops,self.job,{'status':'attended','version':self.job.version})
        self.assertEqual(r.status_code,200,r.content)
        r=self.upload(mark_completed=True);self.assertEqual(r.status_code,201,r.content)
        self.job.refresh_from_db();self.assertEqual(self.job.status,'completed')
