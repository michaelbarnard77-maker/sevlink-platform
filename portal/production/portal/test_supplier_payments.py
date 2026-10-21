import importlib
import json
import uuid
from django.db import connection, transaction, IntegrityError
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from .models import JobInvoice, InvoicePayment, Subcontractor
from .test_attachments import document
from .test_regions import fixtures, assign, SETTINGS
from .test_suppliers import SupplierTests


@override_settings(**SETTINGS)
class SupplierPaymentTests(TestCase):
    @classmethod
    def setUpTestData(cls): fixtures(cls)
    setUp=SupplierTests.setUp

    def upload(self, **changes):
        return self.client.post(reverse('maintenance_invoice',args=[self.job.pk]),{
            'number':'VENDOR-001','amount':'500.00','due_date':str(timezone.localdate()),
            'subcontractor':str(self.partner.pk),'attachments':document(),**changes},
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))

    def pay(self, invoice, amount='200.00', reference='EXTERNAL-TRANSFER', key=None):
        return self.client.post(reverse('maintenance_invoice_payment',args=[self.job.pk,invoice.pk]),
            json.dumps({'version':invoice.version,'amount':amount,'paid_on':str(timezone.localdate()),'reference':reference}),
            content_type='application/json',HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))

    def test_upload_manual_partial_full_payments_and_outstanding_view(self):
        self.assertEqual(assign(self.client,self.job,self.partner).status_code,201)
        response=self.upload();self.assertEqual(response.status_code,201,response.content)
        invoice=JobInvoice.objects.get();self.assertEqual(invoice.subcontractor,self.partner)
        self.assertEqual(invoice.visibility,'internal')
        self.assertEqual(self.pay(invoice).status_code,201)
        invoice.refresh_from_db();self.assertEqual(invoice.payment_status,'partially_paid')
        ledger=self.client.get(reverse('supplier_invoice_ledger')).json()
        self.assertEqual(ledger['count'],1);self.assertEqual(ledger['results'][0]['outstanding'],'300.00')
        self.assertEqual(ledger['results'][0]['payments'][0]['reference'],'EXTERNAL-TRANSFER')
        self.assertEqual(self.pay(invoice,'300.00').status_code,201)
        invoice.refresh_from_db();self.assertEqual(invoice.payment_status,'paid')
        self.assertEqual(self.client.get(reverse('supplier_invoice_ledger')).json()['count'],0)
        self.assertEqual(self.client.get(reverse('supplier_invoice_ledger'),{'state':'paid'}).json()['count'],1)
        profile=self.client.get(reverse('supplier_profile',args=[self.partner.pk])).json()
        self.assertEqual(profile['invoices'][0]['net_paid_amount'],'500.00')

    def test_non_assigned_and_shared_uploads_rejected(self):
        self.assertEqual(self.upload().status_code,400)
        assign(self.client,self.job,self.partner)
        self.assertEqual(self.upload(visibility='shared').status_code,400)
        self.assertEqual(JobInvoice.objects.count(),0)

    def test_duplicate_payments_overpayment_and_reference_requirement(self):
        assign(self.client,self.job,self.partner);self.upload();i=JobInvoice.objects.get()
        self.assertEqual(self.pay(i,reference='').status_code,400)
        key=uuid.uuid4();self.assertEqual(self.pay(i,key=key).status_code,201)
        self.assertEqual(self.pay(i,key=key).status_code,200)
        i.refresh_from_db();self.assertEqual(self.pay(i,'301.00').status_code,400)
        self.assertEqual(InvoicePayment.objects.count(),1)

    def test_supplier_reference_unique_per_supplier_and_private_db_constraint(self):
        assign(self.client,self.job,self.partner);assign(self.client,self.job,self.inland,version=2)
        self.assertEqual(self.upload().status_code,201)
        self.assertEqual(self.upload().status_code,409)
        self.assertEqual(self.upload(subcontractor=str(self.inland.pk)).status_code,201)
        with self.assertRaises(IntegrityError),transaction.atomic():
            JobInvoice.objects.filter(subcontractor=self.partner).update(visibility='shared')

    def test_documents_and_financial_records_hidden_from_pm_tenant_foreign_agency(self):
        assign(self.client,self.job,self.partner);response=self.upload();invoice=JobInvoice.objects.get()
        self.pay(invoice)
        url=response.json()['document']['download_url']
        for user in (self.pm,self.tenant):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse('supplier_invoice_ledger')).status_code,403)
            self.assertEqual(self.client.get(url).status_code,403 if user==self.tenant else 404)
            text=self.client.get(reverse('maintenance_detail',args=[self.job.pk])).content.decode()
            self.assertNotIn('VENDOR-001',text);self.assertNotIn('EXTERNAL-TRANSFER',text)
            self.assertEqual(self.client.get(reverse('maintenance_detail',args=[self.cape_job.pk])).status_code,404)


class BankRemovalMigrationTests(TransactionTestCase):
    def test_nonempty_bank_table_blocks_drop_then_empty_upgrade_preserves_supplier(self):
        old=[('portal','0017_seed_supplier_trades')];new=[('portal','0027_manual_document_references_and_approved_jobs')]
        bank=None
        try:
            MigrationExecutor(connection).migrate(old)
            apps=MigrationExecutor(connection).loader.project_state(old).apps
            user=apps.get_model('portal','User').objects.create(username='bank-removal-test',email='bank-removal@example.test',password='!')
            supplier=apps.get_model('portal','Subcontractor').objects.create(name='Synthetic legacy supplier',created_by=user)
            Bank=apps.get_model('portal','SubcontractorBank')
            bank=Bank.objects.create(subcontractor=supplier,updated_by=user,bank_name='SYNTHETIC',account_holder='SYNTHETIC',account_number='12345678',branch_code='123456',account_type='TEST')
            with self.assertRaisesRegex(RuntimeError,'Banking removal blocked: 1'):
                MigrationExecutor(connection).migrate(new)
            self.assertEqual(Bank.objects.get(pk=bank.pk).account_number,'12345678')
            # Delete this synthetic fixture only, never a user's actual development record.
            bank.delete();bank=None
            MigrationExecutor(connection).migrate(new)
            self.assertNotIn('portal_subcontractorbank',connection.introspection.table_names())
            self.assertTrue(Subcontractor.objects.filter(pk=supplier.pk).exists())
        finally:
            if bank is not None: bank.delete()
            MigrationExecutor(connection).migrate(new)
