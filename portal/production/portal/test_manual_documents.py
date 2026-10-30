"""Externally prepared quotation/invoice PDFs and manual ledger security."""
import hashlib
import json
import tempfile
import uuid
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone
from . import test_notifications as fixtures
from .test_attachments import document, photo
from .models import (JobQuotation, JobInvoice, InvoicePayment, JobActivity, MaintenanceAttachment,
                     OperationsNotification, QuotationAction, Agency, User, Membership, Property, MaintenanceRequest)


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver'],
                   OPERATIONS_EMAIL_DELIVERY_BACKEND=fixtures.LOCAL, OPERATIONS_LIVE_DELIVERY_ENABLED=False)
class ManualDocumentTests(TestCase):
    setUpTestData=classmethod(fixtures.EventWorkflowTests.setUpTestData.__func__)
    post=fixtures.EventWorkflowTests.post
    new_job=fixtures.EventWorkflowTests.new_job

    def setUp(self):
        fixtures.EventWorkflowTests.setUp(self)
        self.new_job();self.client.force_login(self.ops)
        self.invoice_url=reverse('maintenance_invoice',args=[self.job.pk])

    def quote(self, key=None, **changes):
        data=dict(reference='Q-001',amount='1000.00',attachments=document(name='agency-quote.pdf'))
        data.update(changes)
        return self.client.post(self.quote_url,data,HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))

    def invoice(self,key=None,**changes):
        data=dict(number='INV-001',amount='1000.00',due_date='2026-11-15',visibility='shared',attachments=document(name='agency-invoice.pdf'))
        data.update(changes)
        return self.client.post(self.invoice_url,data,HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))

    def sent(self):
        quote=self.quote().json()
        url=reverse('maintenance_quote_action',args=[self.job.pk,quote['id'],'send'])
        response=self.post(url,{'version':quote['version']})
        self.assertEqual(response.status_code,200,response.content)
        return response.json()

    def payment(self,invoice,key=None,**changes):
        data=dict(version=invoice['version'],amount='250.00',paid_on=timezone.localdate().isoformat(),reference='PRIVATE BANK REFERENCE',note='PRIVATE PAYMENT NOTE')
        data.update(changes)
        return self.post(reverse('maintenance_invoice_payment',args=[self.job.pk,invoice['id']]),data,key)

    def body(self,user):
        self.client.force_login(user)
        return self.client.get(self.detail_url).json()

    def download(self,url,expected=200):
        response=self.client.get(url)
        self.assertEqual(response.status_code,expected,b'' if response.streaming else response.content)
        if response.streaming:
            result=b''.join(response.streaming_content)
            self.assertIn('no-store',response['Cache-Control'])
            self.assertEqual(response['Content-Security-Policy'],"default-src 'none'; sandbox")
            return result

    def test_uploaded_quote_original_bytes_hash_date_revision_and_retention(self):
        file=document(name='original.pdf');original=file.read();file.seek(0)
        response=self.quote(attachments=file)
        self.assertEqual(response.status_code,201,response.content)
        quote=response.json()
        self.assertEqual(quote['document']['sha256'],hashlib.sha256(original).hexdigest())
        self.assertEqual(quote['revision'],1)
        self.assertTrue(quote['document']['uploaded_at'])
        self.assertEqual(self.download(quote['document']['download_url']),original)
        quote=self.post(reverse('maintenance_quote_action',args=[self.job.pk,quote['id'],'send']),{'version':quote['version']}).json()
        self.client.force_login(self.pm)
        url=reverse('maintenance_quote_decision',args=[self.job.pk,quote['id']])
        approved=self.post(url,dict(status='approved',reason='Approve original document',version=quote['version']))
        self.assertEqual(approved.status_code,200,approved.content)
        self.assertEqual(self.download(quote['document']['download_url']),original)
        self.assertEqual(OperationsNotification.objects.filter(event__kind='quote_approved').count(),1)
        self.assertEqual(JobActivity.objects.filter(kind='quote_approved').get().actor,self.pm)
        model=JobQuotation.objects.get(pk=quote['id'])
        with self.assertRaises(ProtectedError):
            model.delete()
        with self.assertRaises(ProtectedError):
            MaintenanceAttachment.objects.filter(pk=model.document_id).delete()
        self.assertEqual(model.public_snapshot['document']['sha256'],hashlib.sha256(original).hexdigest())

    def test_revised_pdf_is_distinct_and_old_pdf_remains_downloadable(self):
        quote=self.sent()
        self.client.force_login(self.pm)
        old=self.post(reverse('maintenance_quote_decision',args=[self.job.pk,quote['id']]),dict(status='revision_requested',reason='Please adjust scope',version=quote['version'])).json()
        self.client.force_login(self.ops)
        key=uuid.uuid4()
        from pypdf import PdfWriter
        writer=PdfWriter();writer.add_blank_page(width=300,height=400)
        def revised():
            return self.client.post(reverse('maintenance_quote_action',args=[self.job.pk,quote['id'],'revise']),
                dict(version=old['version'],reference='Q-001-R2',amount='1200',attachments=document(writer,name='revision.pdf')),
                HTTP_IDEMPOTENCY_KEY=str(key))
        response=revised();self.assertEqual(response.status_code,201,response.content)
        new=response.json()
        self.assertEqual(revised().status_code,200)
        self.assertEqual(new['revision'],2)
        self.assertNotEqual(new['document']['sha256'],quote['document']['sha256'])
        self.assertEqual(JobQuotation.objects.get(pk=quote['id']).status,'superseded')
        self.assertTrue(self.download(quote['document']['download_url']).startswith(b'%PDF-'))
        self.client.force_login(self.pm)
        self.download(new['document']['download_url'],404)
        self.assertEqual(self.post(reverse('maintenance_quote_decision',args=[self.job.pk,quote['id']]),dict(version=quote['version'],status='approved',reason='Stale')).status_code,409)
        self.assertEqual(OperationsNotification.objects.filter(event__kind='quote_revision_requested').count(),1)

    def test_quote_create_replay_and_pdf_only_validation(self):
        key=uuid.uuid4()
        self.assertEqual(self.quote(key).status_code,201)
        self.assertEqual(self.quote(key).status_code,200)
        self.assertEqual(self.quote(key,amount='1001').status_code,409)
        for uploaded in (photo(), document(name='fake.jpg')):
            self.assertEqual(self.quote(attachments=uploaded).status_code,400)
        self.assertEqual(self.quote(attachments=[document(),document()]).status_code,400)
        self.assertEqual(self.quote(attachments=[]).status_code,400)
        self.assertEqual(JobQuotation.objects.count(),1)
        self.assertEqual(MaintenanceAttachment.objects.count(),1)

    def test_old_generated_pdf_is_unavailable_and_legacy_approval_blocked(self):
        old=JobQuotation.objects.create(request=self.job,created_by=self.ops,creation_key=uuid.uuid4(),title='Legacy',scope='Historical record',amount='50',status='sent',public_snapshot={'lines':[{'description':'Old'}],'amount':'50'})
        self.client.force_login(self.pm)
        self.download(reverse('maintenance_quote_pdf',args=[self.job.pk,old.pk]),404)
        response=self.post(reverse('maintenance_quote_decision',args=[self.job.pk,old.pk]),dict(version=1,status='approved',reason='No PDF'))
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.client.get(self.detail_url).json()['quotations'][0]['legacy_without_pdf'],True)
        self.assertNotIn('lines',self.client.get(self.detail_url).json()['quotations'][0])
        self.assertEqual(OperationsNotification.objects.count(),0)

    def test_invoice_upload_due_date_and_immutable_header(self):
        response=self.invoice();self.assertEqual(response.status_code,201,response.content)
        invoice=response.json()
        self.assertEqual((invoice['number'],invoice['amount'],invoice['due_date'],invoice['payment_status']),('INV-001','1000.00','2026-11-15','unpaid'))
        self.assertTrue(invoice['uploaded_at'])
        self.assertTrue(self.download(invoice['document']['download_url']).startswith(b'%PDF-'))
        obj=JobInvoice.objects.get()
        obj.amount=Decimal('999')
        with self.assertRaises(ValidationError):obj.save()
        obj.refresh_from_db();obj.document_id=uuid.uuid4()
        with self.assertRaises(ValidationError):obj.save()
        obj.refresh_from_db()
        with self.assertRaises(ProtectedError):MaintenanceAttachment.objects.filter(pk=obj.document_id).delete()
        self.assertEqual(JobActivity.objects.get(kind='invoice_uploaded').actor,self.ops)

    def test_invoice_private_default_scoped_api_and_direct_downloads(self):
        shared=self.invoice().json()
        internal=self.invoice(number='PRIVATE SUPPLIER INV',visibility='internal',amount='300').json()
        response=self.client.post(self.invoice_url,dict(number='PRIVATE DEFAULT',amount='10',due_date='2026-11-15',attachments=document()),HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(response.status_code,201,response.content)
        self.assertEqual(response.json()['visibility'],'internal')
        for user in (self.pm,self.admin):
            data=self.body(user)
            self.assertEqual(len(data['invoices']),1)
            self.assertEqual(data['invoices'][0]['id'],shared['id'])
            self.assertNotIn('PRIVATE',json.dumps(data))
            self.assertNotIn('PRIVATE',self.client.get(self.collection).content.decode())
            self.download(shared['document']['download_url'])
            self.download(internal['document']['download_url'],404)
        for user in (self.tenant,self.foreign,self.other_pm,self.cotenant):
            self.client.force_login(user)
            self.download(shared['document']['download_url'],403 if user == self.tenant else 404)
            self.download(internal['document']['download_url'],403 if user == self.tenant else 404)
        self.assertEqual(self.body(self.tenant)['invoices'],[])
        self.assertFalse(any(e['type'].startswith('invoice_') for e in self.body(self.tenant)['activity']))
        self.assertEqual(len(self.body(self.ops)['invoices']),3)
        self.download(internal['document']['download_url'])

    def test_commercial_pdfs_never_leak_through_general_attachment_routes(self):
        quote=self.sent();invoice=self.invoice().json()
        for user in (self.ops,self.pm,self.admin,self.tenant):
            self.assertEqual(self.body(user)['attachments'],[])
            for doc in (quote['document'],invoice['document']):
                self.download(reverse('maintenance_attachment_download',args=[self.job.pk,doc['id']]),404)
        self.assertEqual(MaintenanceAttachment.objects.filter(purpose='general').count(),0)

    def test_manual_partial_full_payment_replay_private_receipts_and_audit(self):
        invoice=self.invoice().json();key=uuid.uuid4()
        response=self.payment(invoice,key)
        self.assertEqual(response.status_code,201,response.content)
        partial=response.json()
        self.assertEqual((partial['payment_status'],partial['paid_amount'],partial['outstanding']),('partially_paid','250.00','750.00'))
        self.assertEqual(self.payment(invoice,key).status_code,200)
        self.assertEqual(self.payment(invoice,key,amount='300').status_code,409)
        self.assertEqual(self.payment(invoice).status_code,409)
        response=self.payment(partial,amount='750');self.assertEqual(response.status_code,201,response.content)
        paid=response.json()
        self.assertEqual((paid['payment_status'],paid['outstanding']),('paid','0.00'))
        self.assertEqual(self.payment(paid,amount='1').status_code,400)
        self.assertEqual(InvoicePayment.objects.count(),2)
        self.assertEqual(JobActivity.objects.filter(kind='invoice_payment').count(),2)
        receipt=InvoicePayment.objects.first()
        with self.assertRaises(ValidationError):receipt.delete()
        with self.assertRaises(ValidationError):receipt.save()
        for user in (self.pm,self.admin):
            data=self.body(user)
            self.assertEqual(data['invoices'][0]['payment_status'],'paid')
            self.assertNotIn('PRIVATE BANK',json.dumps(data))
            self.assertNotIn('PRIVATE PAYMENT',json.dumps(data))
        # Invoice updates do not silently move job status or emit a staff self-notification.
        self.job.refresh_from_db();self.assertEqual((self.job.status,self.job.version),('awaiting_review',1))
        self.assertEqual(OperationsNotification.objects.count(),0)

    def test_private_supplier_invoice_payment_has_no_external_audit_leak(self):
        invoice=self.invoice(number='PRIVATE SUPPLIER',visibility='internal').json()
        self.assertEqual(self.payment(invoice,amount='1000').status_code,201)
        data=self.body(self.pm)
        self.assertEqual(data['invoices'],[])
        self.assertFalse(any(e['type'].startswith('invoice_') for e in data['activity']))
        self.assertNotIn('PRIVATE',json.dumps(data))
        self.assertEqual(JobActivity.objects.filter(kind__startswith='invoice_',visibility='internal').count(),2)

    def test_only_operations_uploads_and_records_payments_with_current_scope(self):
        invoice=self.invoice().json()
        for user in (self.tenant,self.pm,self.admin,self.foreign,self.other_pm,self.cotenant):
            self.client.force_login(user)
            status=403 if user in (self.tenant,self.pm,self.admin) else 404
            self.assertEqual(self.invoice().status_code,status)
            self.assertEqual(self.quote().status_code,status)
            self.assertEqual(self.payment(invoice).status_code,status)
        self.assertEqual(InvoicePayment.objects.count(),0)

    def test_invalid_invoice_payment_documents_and_duplicate_numbers(self):
        for changes in (dict(amount='NaN'),dict(amount='1.001'),dict(amount='0'),dict(due_date='2026-02-30'),dict(visibility='public'),dict(attachments=photo())):
            self.assertEqual(self.invoice(**changes).status_code,400)
        key=uuid.uuid4();self.assertEqual(self.invoice(key).status_code,201)
        self.assertEqual(self.invoice(key).status_code,200)
        self.assertEqual(self.invoice(key,amount='999').status_code,409)
        self.assertEqual(self.invoice(number='inv-001').status_code,409)
        invoice=JobInvoice.objects.get();data=dict(id=str(invoice.pk),version=invoice.version)
        for changes in (dict(amount='0'),dict(amount='1000.01'),dict(amount='NaN'),dict(amount='1.001'),dict(paid_on='bad'),dict(paid_on=(timezone.localdate()+timedelta(days=1)).isoformat()),dict(version=True)):
            self.assertEqual(self.payment(data,**changes).status_code,400)
        self.assertEqual(InvoicePayment.objects.count(),0)

    def test_upload_and_payment_rollback_cleanup_when_audit_fails(self):
        from .attachments import storage
        with patch('portal.invoices.record',side_effect=RuntimeError('rollback')):
            with self.assertRaises(RuntimeError):self.invoice()
        self.assertEqual(JobInvoice.objects.count(),0)
        self.assertEqual(MaintenanceAttachment.objects.count(),0)
        self.assertEqual(len([p for p in Path(storage().location).rglob('*') if p.is_file()]),0)
        invoice=self.invoice().json()
        with patch('portal.invoices.record',side_effect=RuntimeError('rollback')):
            with self.assertRaises(RuntimeError):self.payment(invoice)
        self.assertEqual(InvoicePayment.objects.count(),0)
        obj=JobInvoice.objects.get();self.assertEqual((obj.paid_amount,obj.payment_status,obj.version),(0,'unpaid',1))
        with patch('portal.quotations.record',side_effect=RuntimeError('rollback')):
            with self.assertRaises(RuntimeError):self.quote()
        self.assertEqual(JobQuotation.objects.count(),0)
        self.assertEqual(MaintenanceAttachment.objects.count(),1)

    def test_internal_supplier_quotation_pdf_stays_in_private_operations_notes(self):
        response=self.client.post(self.comment_url,dict(text='PRIVATE subcontractor quotation and rates',visibility='internal',attachments=document(name='PRIVATE-supplier-quote.pdf')),HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(response.status_code,201,response.content)
        url=response.json()['attachments'][0]['download_url']
        for user in (self.pm,self.admin,self.tenant):
            self.assertNotIn('PRIVATE',json.dumps(self.body(user)))
            self.download(url,404)
        self.body(self.ops);self.download(url)


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver'])
class ConcurrentManualPaymentTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_two_stale_operators_cannot_double_record_or_overpay_invoice(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections, connections
        from django.test import Client
        agency=Agency.objects.create(name='Payment race agency',phone='test',area='test')
        ops=User.objects.create_user(username='payment-race@example.test',email='payment-race@example.test',is_superuser=True)
        prop=Property.objects.create(agency=agency,name='Payment race home',address='Test')
        job=MaintenanceRequest.objects.create(property=prop,reported_by=ops,title='Payment race',description='Test',category='Plumbing')
        attachment=MaintenanceAttachment.objects.create(request=job,uploaded_by=ops,purpose='invoice',visibility='internal',
            storage_key='maintenance/race/invoice.pdf',filename='invoice.pdf',content_type='application/pdf',size=1,sha256='a'*64)
        invoice=JobInvoice.objects.create(request=job,document=attachment,uploaded_by=ops,number='INV-RACE',
            amount='1000',due_date=timezone.localdate(),creation_key=uuid.uuid4(),fingerprint='test')
        barrier=Barrier(2)
        def run(_):
            close_old_connections()
            try:
                client=Client();client.force_login(User.objects.get(pk=ops.pk));barrier.wait(timeout=15)
                return client.post(reverse('maintenance_invoice_payment',args=[job.pk,invoice.pk]),
                    json.dumps(dict(version=1,amount='600',paid_on=timezone.localdate().isoformat())),
                    content_type='application/json',HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())).status_code
            finally:
                connections.close_all()
                # Thread-local healthy persistent connections must also be released.
                for alias in connections:
                    self.assertIsNone(connections[alias].connection)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results=list(executor.map(run,range(2)))
        self.assertEqual(sorted(results),[201,409])
        invoice.refresh_from_db()
        self.assertEqual((invoice.paid_amount,invoice.payment_status,invoice.version),(600,'partially_paid',2))
        self.assertEqual(InvoicePayment.objects.count(),1)
        self.assertEqual(JobActivity.objects.filter(kind='invoice_payment').count(),1)
