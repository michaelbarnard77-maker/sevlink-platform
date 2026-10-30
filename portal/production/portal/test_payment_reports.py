"""Customer payment claims never become bank-confirmed receipts."""
import uuid
from django.test import TestCase, override_settings
from django.urls import reverse
from .test_manual_documents import ManualDocumentTests
from .test_notifications import EventWorkflowTests
from .models import InvoiceAction, InvoicePayment, JobInvoice, OperationsInboxItem, UserJobNotification


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False)
class PaymentReportTests(TestCase):
    setUpTestData=classmethod(EventWorkflowTests.setUpTestData.__func__)
    setUp=ManualDocumentTests.setUp
    new_job=EventWorkflowTests.new_job
    post=EventWorkflowTests.post
    invoice=ManualDocumentTests.invoice
    payment=ManualDocumentTests.payment

    def report(self, invoice, key=None):
        return self.post(reverse('maintenance_invoice_report_paid',args=[self.job.pk,invoice['id']]),
                         {'version':invoice['version']}, key)

    def test_claim_notifies_once_without_changing_money_and_staff_receipt_resolves(self):
        invoice=self.invoice().json()
        self.client.force_login(self.pm)
        key=uuid.uuid4()
        result=self.report(invoice,key)
        self.assertEqual(result.status_code,201,result.content)
        self.assertTrue(result.json()['payment_reported'])
        self.assertEqual(result.json()['payment_status'],'unpaid')
        self.assertEqual(result.json()['outstanding'],'1000.00')
        self.assertEqual(InvoicePayment.objects.count(),0)
        attention=self.client.get(reverse('customer_portal_section',args=['attention'])).json()['items']
        self.assertFalse(any(i.get('target_id')==invoice['id'] for i in attention))
        self.assertEqual(self.report(invoice,key).status_code,200)
        self.assertEqual(self.report(invoice).status_code,200)
        self.assertEqual(InvoiceAction.objects.filter(kind='payment_reported').count(),1)
        inbox=OperationsInboxItem.objects.filter(event__dedup_key__startswith='payment-reported:')
        self.assertEqual(inbox.count(),1)
        self.assertTrue(UserJobNotification.objects.filter(event=inbox.get().event,user=self.ops).exists())
        self.assertFalse(UserJobNotification.objects.filter(event=inbox.get().event,user=self.tenant).exists())
        self.client.force_login(self.ops)
        response=self.payment(invoice,amount='1000')
        self.assertEqual(response.status_code,201,response.content)
        self.assertFalse(response.json()['payment_reported'])
        self.assertEqual(response.json()['payment_status'],'paid')
        self.client.force_login(self.pm)
        self.assertEqual(self.report(response.json()).status_code,409)

    def test_role_scope_private_void_hold_and_stale_guards(self):
        invoice=self.invoice().json()
        for user in (self.tenant,self.ops,self.other_pm,self.foreign):
            self.client.force_login(user)
            self.assertIn(self.report(invoice).status_code,(403,404))
        self.client.force_login(self.ops)
        private=self.invoice(number='SUPPLIER',visibility='internal').json()
        self.client.force_login(self.pm)
        self.assertEqual(self.report(private).status_code,404)
        model=JobInvoice.objects.get(pk=invoice['id'])
        for changes in ({'document_status':'void'},{'document_status':'active','reconciliation_required':True},
                        {'reconciliation_required':False,'version':2}):
            JobInvoice.objects.filter(pk=model.pk).update(**changes)
            self.assertEqual(self.report(invoice).status_code,409)
        self.assertEqual(InvoiceAction.objects.filter(kind='payment_reported').count(),0)

    def test_agency_admin_and_partial_receipt_allow_new_claim(self):
        invoice=self.invoice().json()
        self.client.force_login(self.admin)
        self.assertEqual(self.report(invoice).status_code,201)
        self.client.force_login(self.ops)
        invoice=self.payment(invoice,amount='500').json()
        self.assertFalse(invoice['payment_reported'])
        self.client.force_login(self.pm)
        self.assertEqual(self.report(invoice).status_code,201)
        self.assertEqual(InvoiceAction.objects.filter(kind='payment_reported').count(),2)

    def test_verify_is_staff_only_atomic_versioned_and_idempotent(self):
        invoice=self.invoice().json()
        url=reverse('maintenance_invoice_verify',args=[self.job.pk,invoice['id']])
        for user in (self.pm,self.admin,self.tenant,self.foreign):
            self.client.force_login(user)
            self.assertEqual(self.post(url,{'version':invoice['version']}).status_code,403)
        self.client.force_login(self.ops)
        self.assertEqual(self.post(url,{'version':0}).status_code,400)
        self.assertEqual(self.post(url,{'version':99}).status_code,409)
        JobInvoice.objects.filter(pk=invoice['id']).update(reconciliation_required=True)
        self.assertEqual(self.post(url,{'version':invoice['version']}).status_code,409)
        JobInvoice.objects.filter(pk=invoice['id']).update(reconciliation_required=False)
        key=uuid.uuid4()
        result=self.post(url,{'version':invoice['version']},key)
        self.assertEqual(result.status_code,201,result.content)
        self.assertEqual(result.json()['outstanding'],'0.00')
        self.assertEqual(result.json()['payment_status'],'paid')
        self.assertEqual(self.post(url,{'version':invoice['version']},key).status_code,200)
        self.assertEqual(InvoicePayment.objects.count(),1)
        self.assertEqual(self.post(url,{'version':result.json()['version']}).status_code,409)
