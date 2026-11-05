"""A single upload publishes the original quote PDF and notifies its scoped PM."""
import uuid
from django.test import TestCase,override_settings
from django.urls import reverse
from unittest.mock import patch
from . import test_manual_documents as docs, test_notifications as fixtures
from .test_attachments import document
from .models import JobQuotation,UserJobNotification,QuotationAction,MaintenanceAttachment

@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False)
class QuoteUploadTests(TestCase):
    setUpTestData=classmethod(fixtures.EventWorkflowTests.setUpTestData.__func__)
    setUp=docs.ManualDocumentTests.setUp
    new_job=fixtures.EventWorkflowTests.new_job
    post=fixtures.EventWorkflowTests.post

    def upload(self,key=None,**changes):
        data=dict(reference='QUO-UPLOAD',amount='2600',title='Electrical',scope='Repair sockets',attachments=document())
        data.update(changes)
        return self.client.post(reverse('maintenance_quote_upload',args=[self.job.pk]),data,HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))

    def test_upload_publishes_original_notifies_pm_once_and_requires_approval(self):
        key=uuid.uuid4()
        response=self.upload(key)
        self.assertEqual(response.status_code,201,response.content)
        quote=JobQuotation.objects.get()
        self.assertEqual(quote.status,'sent')
        self.assertIsNotNone(quote.sent_at)
        self.assertFalse(quote.decided_by_id)
        self.assertEqual(quote.amount,2600)
        self.assertEqual(QuotationAction.objects.count(),2)
        self.assertTrue(UserJobNotification.objects.filter(user=self.pm,event__kind='quote_sent',event__request=self.job).exists())
        self.assertFalse(UserJobNotification.objects.filter(user=self.tenant,event__kind='quote_sent').exists())
        self.assertEqual(self.upload(key).status_code,200)
        self.assertEqual(JobQuotation.objects.count(),1)
        self.assertEqual(UserJobNotification.objects.filter(user=self.pm,event__kind='quote_sent').count(),1)
        self.client.force_login(self.pm)
        detail=self.client.get(self.detail_url).json()
        self.assertEqual(detail['quotations'][0]['id'],str(quote.pk))
        self.client.force_login(self.tenant)
        self.assertEqual(self.client.get(self.detail_url).json()['quotations'],[])

    def test_roles_validation_and_failure_are_atomic(self):
        for user in (self.pm,self.admin,self.tenant,self.foreign):
            self.client.force_login(user)
            self.assertIn(self.upload().status_code,(403,404))
        self.client.force_login(self.ops)
        self.assertEqual(self.upload(amount='-1').status_code,400)
        self.assertEqual(self.upload(attachments=[]).status_code,400)
        with patch('portal.quotations.record',side_effect=RuntimeError('notification transaction rollback')):
            with self.assertRaises(RuntimeError):self.upload()
        self.assertEqual(JobQuotation.objects.count(),0)
        self.assertEqual(MaintenanceAttachment.objects.count(),0)
