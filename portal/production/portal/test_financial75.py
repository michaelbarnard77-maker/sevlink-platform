"""Manual financial adjustments, immutable amendment approvals and numbering contracts."""
import json
import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.db import transaction, connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone
from . import test_notifications as fixtures
from . import test_manual_documents as documents
from .models import (JobInvoice, InvoicePayment, InvoiceRefund, InvoiceAction, InvoiceCreditNote,
    JobQuotation, QuotationAction, QuoteApprovalReplacement, JobActivity, OperationsNotification,
    MaintenanceAttachment, DocumentSequence, User, Agency, Property, Membership, MaintenanceRequest)
from .numbering import allocate


@override_settings(SECURE_SSL_REDIRECT=False,ALLOWED_HOSTS=['testserver'],OPERATIONS_EMAIL_DELIVERY_BACKEND=fixtures.LOCAL)
class Financial75Tests(TestCase):
    setUpTestData=classmethod(fixtures.EventWorkflowTests.setUpTestData.__func__)
    new_job=fixtures.EventWorkflowTests.new_job
    post=fixtures.EventWorkflowTests.post
    invoice=documents.ManualDocumentTests.invoice
    quote=documents.ManualDocumentTests.quote
    payment=documents.ManualDocumentTests.payment
    sent=documents.ManualDocumentTests.sent
    body=documents.ManualDocumentTests.body
    download=documents.ManualDocumentTests.download

    def setUp(self):
        fixtures.EventWorkflowTests.setUp(self)
        self.new_job();self.client.force_login(self.ops)
        self.invoice_url=reverse('maintenance_invoice',args=[self.job.pk])

    def paid(self,visibility='shared',amount='1000'):
        invoice=self.invoice(visibility=visibility).json()
        response=self.payment(invoice,amount=amount)
        self.assertEqual(response.status_code,201,response.content)
        return response.json()

    def adjust(self,invoice,operation,key=None,**values):
        return self.post(reverse('maintenance_invoice_adjustment',args=[self.job.pk,invoice['id'],operation]),dict(version=invoice['version'],**values),key)

    def refund(self,invoice,key=None,**changes):
        data=dict(payment_id=invoice['payments'][0]['id'],amount='250',refunded_on=timezone.localdate().isoformat(),
                  reason='PRIVATE refund reason',reference='PRIVATE REFUND REFERENCE',confirmation='REFUND')
        data.update(changes)
        return self.adjust(invoice,'refunds',key,**data)

    def void(self,invoice,key=None,**changes):
        data=dict(reason='PRIVATE void reason',voided_on=timezone.localdate().isoformat(),accounting_reference='PRIVATE ACCOUNTING REF',accounting_reviewed=True,confirmation='VOID')
        data.update(changes)
        return self.adjust(invoice,'void',key,**data)

    def correct(self,invoice,key=None,**changes):
        data=dict(version=invoice['version'],number='CORRECTED-EXT-002',amount='900',due_date='2026-12-01',reason='PRIVATE correction reason',attachments=fixtures.document(name='replacement.pdf'))
        data.update(changes)
        return self.client.post(reverse('maintenance_invoice_adjustment',args=[self.job.pk,invoice['id'],'correct']),data,HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))

    def reconcile(self,invoice):
        return self.adjust(invoice,'reconcile',reason='Accountant reviewed original funds and documents',reference='PRIVATE RECONCILIATION REF',confirmation='RECONCILE')

    def approve(self,quote,status='approved',key=None):
        self.client.force_login(self.pm)
        return self.post(reverse('maintenance_quote_decision',args=[self.job.pk,quote['id']]),dict(version=quote['version'],status=status,reason='Agency decision comment'),key)

    def amendment(self,quote,key=None,operation='amend',**changes):
        self.client.force_login(self.ops)
        data=dict(version=quote['version'],reference='EXTERNAL-AMENDMENT-2',amount='1200',reason='Updated public scope',attachments=fixtures.document(name='amended.pdf'))
        data.update(changes)
        return self.client.post(reverse('maintenance_quote_action',args=[self.job.pk,quote['id'],operation]),data,HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))

    def send(self,quote):
        self.client.force_login(self.ops)
        return self.post(reverse('maintenance_quote_action',args=[self.job.pk,quote['id'],'send']),dict(version=quote['version'])).json()

    def test_partial_full_refunds_preserve_payments_and_net_totals(self):
        invoice=self.paid();payment=InvoicePayment.objects.get();original=InvoicePayment.objects.values().get()
        result=self.refund(invoice);self.assertEqual(result.status_code,201,result.content)
        partial=result.json()
        self.assertEqual((partial['paid_amount'],partial['refunded_amount'],partial['net_paid_amount'],partial['outstanding'],partial['payment_status']),('1000.00','250.00','750.00','250.00','partially_paid'))
        result=self.refund(partial,amount='750');self.assertEqual(result.status_code,201,result.content)
        full=result.json()
        self.assertEqual((full['net_paid_amount'],full['outstanding'],full['payment_status']),('0.00','1000.00','refunded'))
        self.assertEqual(InvoicePayment.objects.values().get(),original)
        self.assertEqual(InvoiceRefund.objects.count(),2)
        self.assertEqual(JobActivity.objects.filter(kind='invoice_refund').count(),2)
        self.assertEqual(InvoiceRefund.objects.first().payment,payment)
        for refund in InvoiceRefund.objects.all():
            with self.assertRaises(ValidationError):refund.save()
            with self.assertRaises(ValidationError):refund.delete()
        # Refunds free eligible balance for a later genuinely received payment.
        self.assertEqual(self.payment(full,amount='1000').status_code,201)
        obj=JobInvoice.objects.get();self.assertEqual((obj.paid_amount,obj.refunded_amount,obj.payment_status),(2000,1000,'paid'))

    def test_refund_confirmation_limits_date_replay_stale_and_original_payment_scope(self):
        invoice=self.paid();key=uuid.uuid4()
        self.assertEqual(self.refund(invoice,confirmation='').status_code,400)
        for changes in (dict(amount='1000.01'),dict(amount='0'),dict(amount='NaN'),dict(amount='1.001'),dict(payment_id=True),dict(refunded_on=(timezone.localdate()+timedelta(days=1)).isoformat()),dict(refunded_on='2020-01-01')):
            self.assertEqual(self.refund(invoice,**changes).status_code,400)
        self.assertEqual(self.refund(invoice,key).status_code,201)
        self.assertEqual(self.refund(invoice,key).status_code,200)
        self.assertEqual(self.refund(invoice,key,amount='200').status_code,409)
        self.assertEqual(self.refund(invoice).status_code,409)
        self.assertEqual(InvoiceRefund.objects.count(),1)
        other=self.invoice(number='OTHER').json();other=self.payment(other,amount='100').json()
        self.assertEqual(self.refund(other,payment_id=invoice['payments'][0]['id'],amount='10').status_code,404)
        self.assertEqual(InvoiceRefund.objects.count(),1)

    def test_refund_eligibility_is_per_payment_not_just_invoice_total(self):
        invoice=self.paid(amount='300');invoice=self.payment(invoice,amount='700').json()
        self.assertEqual(self.refund(invoice,amount='301').status_code,400)
        refunded=self.refund(invoice,amount='300').json()
        self.assertEqual(self.refund(refunded,amount='1').status_code,400)
        self.assertEqual(self.refund(refunded,payment_id=refunded['payments'][1]['id'],amount='700').status_code,201)

    def test_paid_void_correction_refund_and_explicit_reconciliation_holds(self):
        invoice=self.paid();pdf=self.download(invoice['document']['download_url'])
        void=self.void(invoice);self.assertEqual(void.status_code,201,void.content)
        old=void.json()
        self.assertEqual((old['document_status'],old['reconciliation_required'],old['outstanding'],old['collectible']),('void',True,'0.00','0.00'))
        self.assertEqual(self.payment(old,amount='1').status_code,409)
        self.assertEqual(self.reconcile(old).status_code,409)
        corrected=self.correct(old);self.assertEqual(corrected.status_code,201,corrected.content)
        new=corrected.json()
        self.assertEqual((new['previous_id'],new['reconciliation_required'],new['net_paid_amount']),(old['id'],True,'0.00'))
        self.assertEqual(self.payment(new,amount='100').status_code,409)
        self.assertEqual(self.reconcile(new).status_code,409)
        self.assertEqual(InvoicePayment.objects.count(),1)
        refunded=self.refund(old,amount='1000').json()
        self.assertTrue(refunded['reconciliation_required'])
        self.assertEqual(self.download(old['document']['download_url']),pdf)
        released=self.reconcile(refunded);self.assertEqual(released.status_code,201,released.content)
        self.assertEqual(self.reconcile(new).status_code,201)
        refreshed=self.client.get(self.detail_url).json()['invoices'][-1]
        self.assertEqual(self.payment(refreshed,amount='900').status_code,201)
        original=JobInvoice.objects.get(pk=old['id'])
        self.assertEqual((original.document_status,original.paid_amount,original.refunded_amount),('void',1000,1000))
        self.assertEqual(original.voided_by,self.ops)
        self.assertEqual(original.voided_on,timezone.localdate())
        original.void_reason='Rewrite'
        with self.assertRaises(ValidationError):original.save()

    def test_unpaid_void_correction_duplicate_confirmation_and_pdf_validation(self):
        invoice=self.invoice().json();key=uuid.uuid4()
        self.assertEqual(self.void(invoice,confirmation='').status_code,400)
        self.assertEqual(self.void(invoice,accounting_reviewed=False).status_code,400)
        self.assertEqual(self.void(invoice,key).status_code,201)
        self.assertEqual(self.void(invoice,key).status_code,200)
        self.assertEqual(self.void(invoice,key,reason='different').status_code,409)
        old=self.client.get(self.detail_url).json()['invoices'][0]
        self.assertFalse(old['reconciliation_required'])
        self.assertEqual(self.correct(old,number=old['number']).status_code,409)
        from .test_attachments import photo
        self.assertEqual(self.correct(old,attachments=photo()).status_code,400)
        key=uuid.uuid4();result=self.correct(old,key)
        self.assertEqual(result.status_code,201,result.content)
        self.assertEqual(self.correct(old,key).status_code,200)
        self.assertEqual(self.correct(old).status_code,409)
        self.assertFalse(result.json()['reconciliation_required'])
        self.assertEqual(self.payment(result.json(),amount='900').status_code,201)
        self.assertEqual(JobInvoice.objects.count(),2)

    def test_credit_note_is_uploaded_paperwork_and_does_not_double_adjust_ledger(self):
        invoice=self.paid()
        url=reverse('maintenance_invoice_adjustment',args=[self.job.pk,invoice['id'],'credit-notes'])
        key=uuid.uuid4()
        def upload():
            return self.client.post(url,dict(version=invoice['version'],reference='CN-EXT-001',amount='1000',issued_on=timezone.localdate().isoformat(),reason='PRIVATE accounting reason',attachments=fixtures.document(name='credit.pdf')),HTTP_IDEMPOTENCY_KEY=str(key))
        result=upload();self.assertEqual(result.status_code,201,result.content)
        self.assertEqual(upload().status_code,200)
        self.assertEqual(InvoiceCreditNote.objects.count(),1)
        obj=JobInvoice.objects.get();self.assertEqual((obj.paid_amount,obj.refunded_amount),(1000,0))
        note=result.json()['credit_notes'][0]
        self.assertTrue(self.download(note['document']['download_url']).startswith(b'%PDF-'))
        self.body(self.pm);self.download(note['document']['download_url'])
        self.client.force_login(self.foreign);self.download(note['document']['download_url'],404)
        self.body(self.tenant);self.download(note['document']['download_url'],403)
        self.assertEqual(self.client.get(reverse('maintenance_attachment_download',args=[self.job.pk,note['document']['id']])).status_code,404)

    def test_privacy_and_permission_boundaries_for_all_adjustments(self):
        invoice=self.paid(visibility='internal')
        refunded=self.refund(invoice).json();voided=self.void(refunded).json();replacement=self.correct(voided).json()
        for user in (self.pm,self.admin,self.tenant):
            data=self.body(user)
            self.assertEqual(data['invoices'],[])
            self.assertNotIn('PRIVATE',json.dumps(data))
            self.assertFalse(any(e['type'].startswith('invoice_') for e in data['activity']))
        for user in (self.pm,self.admin,self.tenant,self.foreign,self.other_pm,self.cotenant):
            self.client.force_login(user);status=403 if user in (self.pm,self.admin,self.tenant) else 404
            self.assertEqual(self.refund(voided).status_code,status)
            self.assertEqual(self.void(voided).status_code,status)
            self.assertEqual(self.correct(voided).status_code,status)
            self.assertEqual(self.reconcile(replacement).status_code,status)
        self.body(self.ops)
        shared=self.paid()
        changed=self.refund(shared).json();self.void(changed)
        for user in (self.pm,self.admin):
            data=self.body(user)
            self.assertNotIn('PRIVATE',json.dumps(data))
            self.assertEqual(len(data['invoices']),1)

    def test_adjustment_audit_failure_rolls_back_refund_and_file(self):
        invoice=self.paid()
        with patch('portal.financial.record',side_effect=RuntimeError('rollback')):
            with self.assertRaises(RuntimeError):self.refund(invoice)
        self.assertEqual(InvoiceRefund.objects.count(),0)
        self.assertEqual(JobInvoice.objects.get().refunded_amount,0)
        old=self.void(invoice).json();before=MaintenanceAttachment.objects.count()
        with patch('portal.financial.record',side_effect=RuntimeError('rollback')):
            with self.assertRaises(RuntimeError):self.correct(old)
        self.assertEqual(MaintenanceAttachment.objects.count(),before)
        self.assertEqual(JobInvoice.objects.count(),1)

    def test_approved_amendment_retains_original_until_fresh_approval(self):
        original=self.approve(self.sent()).json()
        saved=JobQuotation.objects.values().get(pk=original['id'])
        original_actions=QuotationAction.objects.filter(quote_id=original['id']).count()
        pending=self.amendment(original).json()
        self.assertEqual(pending['amends_id'],original['id'])
        self.assertEqual(pending['revision'],original['revision']+1)
        self.assertTrue(self.body(self.ops)['quotations'][0]['approval_valid'])
        self.assertEqual(self.body(self.pm)['quotations'][0]['id'],original['id'])
        self.assertEqual(len(self.body(self.pm)['quotations']),1)  # Amendment draft is private.
        pending=self.send(pending);key=uuid.uuid4()
        accepted=self.approve(pending,key=key);self.assertEqual(accepted.status_code,200,accepted.content)
        self.assertEqual(self.approve(pending,key=key).status_code,200)
        self.assertEqual(self.approve(pending).status_code,409)
        self.assertEqual(QuoteApprovalReplacement.objects.count(),1)
        self.assertEqual(JobQuotation.objects.values().get(pk=original['id']),saved)
        self.assertEqual(QuotationAction.objects.filter(quote_id=original['id']).count(),original_actions)
        data=self.body(self.pm)['quotations']
        self.assertFalse(data[0]['approval_valid']);self.assertTrue(data[1]['approval_valid'])
        self.assertEqual(data[0]['superseded_by_approval'],pending['id'])
        self.assertEqual(OperationsNotification.objects.filter(event__kind='quote_approved').count(),2)
        self.assertTrue(self.download(original['document']['download_url']).startswith(b'%PDF-'))

    def test_rejected_and_revision_requested_amendments_do_not_remove_original_approval(self):
        original=self.approve(self.sent()).json();key=uuid.uuid4()
        pending=self.amendment(original,key).json()
        self.assertEqual(self.amendment(original,key).status_code,200)
        self.assertEqual(self.amendment(original).status_code,409)
        rejected=self.approve(self.send(pending),'rejected').json()
        self.assertTrue(self.body(self.pm)['quotations'][0]['approval_valid'])
        revised=self.amendment(rejected,operation='revise').json()
        self.assertEqual(revised['amends_id'],original['id'])
        decided=self.approve(self.send(revised),'revision_requested')
        self.assertEqual(decided.status_code,200,decided.content)
        self.assertEqual(QuoteApprovalReplacement.objects.count(),0)
        self.assertEqual(OperationsNotification.objects.filter(event__kind='quote_rejected').count(),1)
        self.assertEqual(OperationsNotification.objects.filter(event__kind='quote_revision_requested').count(),1)
        self.assertTrue(self.body(self.pm)['quotations'][0]['approval_valid'])

    def test_amendment_agency_boundaries_and_required_uploaded_reason(self):
        original=self.approve(self.sent()).json()
        self.assertEqual(self.amendment(original,reason='').status_code,400)
        pending=self.send(self.amendment(original).json())
        for user in (self.foreign,self.other_pm,self.cotenant,self.tenant,self.ops):
            self.client.force_login(user)
            expected=403 if user in (self.tenant,self.ops) else 404
            response=self.post(reverse('maintenance_quote_decision',args=[self.job.pk,pending['id']]),dict(version=pending['version'],status='approved',reason='Forbidden'))
            self.assertEqual(response.status_code,expected)
        self.assertEqual(QuoteApprovalReplacement.objects.count(),0)

    def test_internal_numbering_annual_sequences_external_references_and_idempotency(self):
        with patch('portal.numbering.timezone.localdate',return_value=date(2031,12,31)):
            quote=self.quote(reference='EXTERNAL-PDF-REF').json();invoice=self.invoice(number='ACCOUNTANT-REF').json()
            self.assertEqual((quote['record_number'],invoice['record_number']),('SQ-2031-0001','SI-2031-0001'))
            self.assertEqual((quote['reference'],invoice['number']),('EXTERNAL-PDF-REF','ACCOUNTANT-REF'))
            self.assertEqual(self.quote().json()['record_number'],'SQ-2031-0002')
        with patch('portal.numbering.timezone.localdate',return_value=date(2032,1,1)):
            self.assertEqual(self.quote().json()['record_number'],'SQ-2032-0001')
            self.assertEqual(self.invoice(number='NEXT-EXTERNAL').json()['record_number'],'SI-2032-0001')
        key=uuid.uuid4();one=self.quote(key).json();self.assertEqual(self.quote(key).json()['record_number'],one['record_number'])
        self.assertEqual(JobQuotation.objects.filter(record_number=one['record_number']).count(),1)
        with patch('portal.numbering.timezone.localdate',return_value=date(2033,1,1)):
            DocumentSequence.objects.create(prefix='SQ',year=2033,last_value=9999)
            before=MaintenanceAttachment.objects.count()
            self.assertEqual(self.quote().status_code,400)
            self.assertEqual(MaintenanceAttachment.objects.count(),before)


@override_settings(SECURE_SSL_REDIRECT=False,ALLOWED_HOSTS=['testserver'])
class FinancialConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.agency=Agency.objects.create(name='Concurrency',phone='test',area='test')
        self.ops=User.objects.create_user(username='finance-race@example.test',email='finance-race@example.test',is_superuser=True)
        self.pm=User.objects.create_user(username='finance-pm@example.test',email='finance-pm@example.test')
        Membership.objects.create(user=self.pm,agency=self.agency,role='pm')
        self.home=Property.objects.create(agency=self.agency,manager=self.pm,name='Test',address='Test')
        self.job=MaintenanceRequest.objects.create(property=self.home,reported_by=self.ops,title='Race',description='Test',category='Plumbing')

    def attachment(self,purpose):
        return MaintenanceAttachment.objects.create(request=self.job,uploaded_by=self.ops,purpose=purpose,visibility='internal',
            storage_key=f'maintenance/{self.job.pk}/{uuid.uuid4()}.pdf',filename='test.pdf',content_type='application/pdf',size=1,sha256='a'*64)

    def invoice(self,paid=0):
        invoice=JobInvoice.objects.create(request=self.job,document=self.attachment('invoice'),uploaded_by=self.ops,
            number='Race',amount='1000',due_date=timezone.localdate(),paid_amount=paid,payment_status='paid' if paid==1000 else 'unpaid',creation_key=uuid.uuid4(),fingerprint='test')
        if paid:
            payment=InvoicePayment.objects.create(invoice=invoice,actor=self.ops,amount=paid,paid_on=timezone.localdate(),key=uuid.uuid4(),fingerprint='test')
            return invoice,payment
        return invoice

    def race(self,operations,user=None):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections,close_old_connections
        from django.test import Client
        barrier=Barrier(2);user_id=(user or self.ops).pk
        def run(operation):
            close_old_connections()
            try:
                client=Client();client.force_login(User.objects.get(pk=user_id));barrier.wait(timeout=15)
                return operation(client)
            finally:
                connections.close_all()
                for alias in connections:
                    self.assertIsNone(connections[alias].connection)
        with ThreadPoolExecutor(max_workers=2) as executor:
            return list(executor.map(run,operations))

    def api(self,client,url,data):
        return client.post(url,json.dumps(data),content_type='application/json',HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())).status_code

    @skipUnlessDBFeature('has_select_for_update')
    def test_two_full_refunds_only_one_can_consume_original_payment(self):
        invoice,payment=self.invoice(1000)
        url=reverse('maintenance_invoice_adjustment',args=[self.job.pk,invoice.pk,'refunds'])
        body=dict(version=1,payment_id=payment.pk,amount='1000',refunded_on=timezone.localdate().isoformat(),reason='Race refund',reference='External reference',confirmation='REFUND')
        results=self.race([lambda c:self.api(c,url,body)]*2)
        self.assertEqual(sorted(results),[201,409])
        self.assertEqual(InvoiceRefund.objects.count(),1)
        invoice.refresh_from_db();self.assertEqual((invoice.paid_amount,invoice.refunded_amount,invoice.payment_status),(1000,1000,'refunded'))
        self.assertEqual(InvoicePayment.objects.get().amount,1000)

    @skipUnlessDBFeature('has_select_for_update')
    def test_void_and_payment_from_same_version_have_one_winner(self):
        invoice=self.invoice()
        void_url=reverse('maintenance_invoice_adjustment',args=[self.job.pk,invoice.pk,'void'])
        pay_url=reverse('maintenance_invoice_payment',args=[self.job.pk,invoice.pk])
        results=self.race([
            lambda c:self.api(c,void_url,dict(version=1,reason='Void externally',voided_on=timezone.localdate().isoformat(),accounting_reference='Accountant',accounting_reviewed=True,confirmation='VOID')),
            lambda c:self.api(c,pay_url,dict(version=1,amount='1000',paid_on=timezone.localdate().isoformat()))])
        self.assertEqual(sorted(results),[201,409]);invoice.refresh_from_db()
        self.assertFalse(invoice.document_status=='void' and invoice.paid_amount>0)

    @skipUnlessDBFeature('has_select_for_update')
    def test_simultaneous_amendment_approvals_replace_once(self):
        base=JobQuotation.objects.create(request=self.job,document=self.attachment('quotation'),created_by=self.ops,creation_key=uuid.uuid4(),title='Original',scope='Public',amount='1000',status='approved')
        amendment=JobQuotation.objects.create(request=self.job,document=self.attachment('quotation'),created_by=self.ops,creation_key=uuid.uuid4(),title='Amendment',scope='Public',amount='1200',status='sent',previous=base,amends=base,series_id=base.series_id,revision=2,amendment_reason='Public scope change')
        url=reverse('maintenance_quote_decision',args=[self.job.pk,amendment.pk])
        body=dict(version=1,status='approved',reason='Approve change')
        self.assertEqual(sorted(self.race([lambda c:self.api(c,url,body)]*2,user=self.pm)),[200,409])
        self.assertEqual(QuoteApprovalReplacement.objects.count(),1)
        self.assertEqual(OperationsNotification.objects.count(),1)
        base.refresh_from_db();self.assertEqual((base.status,base.amount,base.version),('approved',1000,1))

    @skipUnlessDBFeature('has_select_for_update')
    def test_concurrent_first_annual_numbers_are_unique(self):
        def reserve(_):
            with transaction.atomic():return allocate('SQ')
        values=self.race([reserve,reserve])
        year=timezone.localdate().year
        self.assertEqual(set(values),{f'SQ-{year}-0001',f'SQ-{year}-0002'})


class Financial75MigrationTests(TransactionTestCase):
    def test_preserves_paid_invoice_approved_quote_and_reserves_historical_ranges(self):
        old=[('portal','0010_jobquotation_document_jobquotation_reference_and_more')]
        new=[('portal','0017_seed_supplier_trades')]
        try:
            executor=MigrationExecutor(connection);executor.migrate(old)
            apps=executor.loader.project_state(old).apps
            user=apps.get_model('portal','User').objects.create(username='legacy-finance@example.test',email='legacy-finance@example.test',password='!')
            agency=apps.get_model('portal','Agency').objects.create(name='Legacy finance',phone='test',area='test')
            home=apps.get_model('portal','Property').objects.create(agency=agency,name='Legacy',address='Test')
            job=apps.get_model('portal','MaintenanceRequest').objects.create(property=home,reported_by=user,title='Existing',description='Test',category='Plumbing')
            file=apps.get_model('portal','MaintenanceAttachment').objects.create(request=job,uploaded_by=user,purpose='invoice',visibility='internal',storage_key='legacy.pdf',filename='legacy.pdf',content_type='application/pdf',size=1,sha256='a'*64)
            invoice=apps.get_model('portal','JobInvoice').objects.create(request=job,document=file,uploaded_by=user,number='SI-2024-0010',amount='100',paid_amount='25',payment_status='partially_paid',due_date='2024-12-01',creation_key=uuid.uuid4(),fingerprint='existing')
            payment=apps.get_model('portal','InvoicePayment').objects.create(invoice=invoice,actor=user,amount='25',paid_on='2024-11-01',key=uuid.uuid4(),fingerprint='existing')
            quote=apps.get_model('portal','JobQuotation').objects.create(request=job,created_by=user,reference='SQ-2024-0042',title='Original approved',scope='Preserve',amount='100',status='approved',creation_key=uuid.uuid4(),public_snapshot={'amount':'100','legacy':'unchanged'})
            executor=MigrationExecutor(connection);executor.migrate(new)
            apps=executor.loader.project_state(new).apps
            invoice=apps.get_model('portal','JobInvoice').objects.get(pk=invoice.pk)
            self.assertEqual((invoice.number,invoice.record_number,invoice.paid_amount,invoice.refunded_amount,invoice.document_status),('SI-2024-0010',None,25,0,'active'))
            self.assertEqual(apps.get_model('portal','InvoicePayment').objects.get(pk=payment.pk).amount,25)
            quote=apps.get_model('portal','JobQuotation').objects.get(pk=quote.pk)
            self.assertEqual((quote.reference,quote.record_number,quote.status),('SQ-2024-0042',None,'approved'))
            self.assertEqual(quote.public_snapshot,{'amount':'100','legacy':'unchanged'})
            self.assertEqual(apps.get_model('portal','InvoiceRefund').objects.count(),0)
            self.assertEqual(apps.get_model('portal','OperationsNotification').objects.count(),0)
            with patch('portal.numbering.timezone.localdate',return_value=date(2024,12,31)),transaction.atomic():
                self.assertEqual((allocate('SQ'),allocate('SI')),('SQ-2024-0043','SI-2024-0011'))
        finally:MigrationExecutor(connection).migrate(new)
