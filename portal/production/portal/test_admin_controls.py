"""Explicit administrator overrides and scoped removals use isolated synthetic records."""
import uuid
from unittest.mock import patch
from django.test import TestCase,override_settings
from django.urls import reverse
from . import models as m, test_manual_documents as docs, test_notifications as fixtures

@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False)
class AdminControlTests(TestCase):
    setUpTestData=classmethod(fixtures.EventWorkflowTests.setUpTestData.__func__)
    setUp=docs.ManualDocumentTests.setUp
    new_job=fixtures.EventWorkflowTests.new_job
    post=fixtures.EventWorkflowTests.post
    invoice=docs.ManualDocumentTests.invoice
    quote=docs.ManualDocumentTests.quote

    def removal(self,kind,pk):return reverse('admin_remove',args=[kind,pk])

    def test_override_booked_closed_reopen_audited_without_fake_finance(self):
        self.invoice()
        url=reverse('manual_job_move',args=[self.job.pk])
        for user in (self.pm,self.admin,self.tenant):
            self.client.force_login(user)
            self.assertEqual(self.post(url,dict(version=1,stage='closed',reason='Test')).status_code,403)
        self.client.force_login(self.ops)
        self.assertEqual(self.post(url,dict(version=1,stage='closed',reason='')).status_code,400)
        for target in ('booked','closed','quoting'):
            self.job.refresh_from_db();version=self.job.version;key=uuid.uuid4()
            values=dict(version=version,stage=target,reason='PRIVATE MANUAL OVERRIDE REASON')
            response=self.post(url,values,key)
            self.assertEqual(response.status_code,200,response.content)
            self.assertEqual(response.json()['workflow']['stage'],target)
            self.assertEqual(self.post(url,values,key).status_code,200)
            self.job.refresh_from_db();self.assertEqual(self.job.version,version+1)
        self.assertEqual(m.InvoicePayment.objects.count(),0)
        self.assertEqual(m.TeamAppointment.objects.count(),0)
        self.assertEqual(m.WorkflowDecision.objects.filter(operation='manual-stage').count(),3)
        self.client.force_login(self.pm)
        self.assertNotIn('PRIVATE MANUAL OVERRIDE REASON',self.client.get(self.detail_url).content.decode())
        self.assertEqual(self.post(url,values).status_code,403)

    def test_tenant_removal_clears_identity_login_and_invites_keeps_jobs_and_invoices(self):
        self.invoice()
        tenancy=m.Tenancy.objects.filter(user=self.tenant).first()
        if not tenancy:tenancy=m.Tenancy.objects.create(property=self.home,user=self.tenant,name='Tenant personal name',email=self.tenant.email,phone='PRIVATE PHONE')
        from datetime import timedelta
        from django.utils import timezone
        for index in range(2):
            m.Invitation.objects.create(agency=self.agency,email=self.tenant.email,name='Personal name',role='tenant',tenancy=tenancy,token_hash=str(uuid.uuid4()),expires_at=timezone.now()+timedelta(days=1),invited_by=self.ops)
        self.client.force_login(self.tenant)
        old_session=self.client.cookies['sessionid'].value
        self.client.force_login(self.ops);url=self.removal('tenant',tenancy.pk)
        preview=self.client.get(url).json()
        self.assertTrue(preview['keeps_jobs'])
        self.assertEqual(self.post(url,dict(token=preview['token'],confirmation='REMOVE')).status_code,200)
        self.tenant.refresh_from_db();tenancy.refresh_from_db()
        self.assertFalse(self.tenant.is_active);self.assertFalse(self.tenant.has_usable_password())
        self.assertEqual(self.tenant.first_name,'Removed account');self.assertTrue(self.tenant.email.endswith('@removed.invalid'))
        self.assertEqual((tenancy.name,tenancy.phone,tenancy.active),('Removed tenant','',False))
        self.assertEqual(m.MaintenanceRequest.objects.count(),1);self.assertEqual(m.JobInvoice.objects.count(),1)
        self.assertEqual(set(m.Invitation.objects.values_list('email',flat=True)),{self.tenant.email})
        self.assertEqual(m.Invitation.objects.filter(revoked_at__isnull=False).count(),2)
        from django.contrib.sessions.models import Session
        self.assertFalse(Session.objects.filter(session_key=old_session).exists())

    def test_property_purge_preserves_other_properties_staff_and_protected_finance_elsewhere(self):
        self.invoice()
        self.assertEqual(self.quote(reference='SQ-REMOVE').status_code,201)
        other=m.Property.objects.create(agency=self.agency,name='Keep home',address='Keep address',manager=self.pm)
        survivor=m.MaintenanceRequest.objects.create(property=other,reported_by=self.pm,title='Keep repair',description='Synthetic',category='Plumbing')
        keep=self.client.post(reverse('maintenance_invoice',args=[survivor.pk]),dict(number='INV-KEEP',amount='500',visibility='shared',due_date='2026-11-15',attachments=docs.document()),HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(keep.status_code,201,keep.content)
        keep_invoice=m.JobInvoice.objects.get(pk=keep.json()['id']);keep_key=keep_invoice.document.storage_key
        url=self.removal('property',self.home.pk)
        for user in (self.pm,self.admin,self.tenant,self.foreign):
            self.client.force_login(user);self.assertEqual(self.client.get(url).status_code,403)
        self.client.force_login(self.ops);preview=self.client.get(url).json()
        self.assertEqual(preview['counts']['Invoices'],1)
        self.assertEqual(self.post(url,dict(token=preview['token'],confirmation='NO')).status_code,400)
        self.assertTrue(m.Property.objects.filter(pk=self.home.pk).exists())
        with self.captureOnCommitCallbacks(execute=True):
            result=self.post(url,dict(token=preview['token'],confirmation='REMOVE'))
        self.assertEqual(result.status_code,200,result.content)
        self.assertFalse(m.MaintenanceRequest.objects.filter(pk=self.job.pk).exists())
        self.assertTrue(m.MaintenanceRequest.objects.filter(pk=survivor.pk).exists())
        self.assertTrue(m.JobInvoice.objects.filter(pk=keep_invoice.pk).exists())
        from .attachments import storage
        self.assertTrue(storage().exists(keep_key))
        self.assertTrue(m.User.objects.get(pk=self.ops.pk).is_active)
        self.assertFalse(m.QuotationReferenceReservation.objects.filter(reference='sq-remove').exists())
        self.assertEqual(m.RemovalReceipt.objects.count(),1)

    def test_stale_preview_and_atomic_failure_cannot_remove_anything(self):
        url=self.removal('property',self.home.pk)
        self.client.force_login(self.ops);preview=self.client.get(url).json()
        self.job.title='Changed repair';self.job.save(update_fields=['title'])
        self.assertEqual(self.post(url,dict(token=preview['token'],confirmation='REMOVE')).status_code,409)
        preview=self.client.get(url).json()
        with patch('portal.admin_controls.m.RemovalReceipt.objects.create',side_effect=RuntimeError('Rollback')):
            with self.assertRaises(RuntimeError):self.post(url,dict(token=preview['token'],confirmation='REMOVE'))
        self.assertTrue(m.Property.objects.filter(pk=self.home.pk).exists())
        self.assertTrue(m.MaintenanceRequest.objects.filter(pk=self.job.pk).exists())
        self.assertEqual(m.RemovalReceipt.objects.count(),0)

    def test_agency_purge_and_cleanup_retry(self):
        invoice=self.invoice().json();doc=m.MaintenanceAttachment.objects.get(pk=invoice['document']['id']) if 'id' in invoice['document'] else m.MaintenanceAttachment.objects.get(purpose='invoice')
        key=doc.storage_key
        self.client.force_login(self.ops);url=self.removal('agency',self.agency.pk)
        preview=self.client.get(url).json()
        with patch('portal.admin_controls.attachments.storage') as storage:
            storage.return_value.delete.side_effect=OSError('Test storage outage')
            with self.captureOnCommitCallbacks(execute=True):response=self.post(url,dict(token=preview['token'],confirmation='REMOVE'))
        self.assertEqual(response.status_code,200,response.content)
        receipt=m.RemovalReceipt.objects.get();self.assertIn(key,receipt.pending_files)
        self.assertFalse(m.Agency.objects.filter(pk=self.agency.pk).exists())
        self.assertTrue(m.Agency.objects.filter(pk=self.foreign_agency.pk).exists())
        self.assertTrue(m.User.objects.get(pk=self.ops.pk).is_active)
        cleanup=reverse('removal_cleanup',args=[receipt.pk]);self.assertEqual(self.post(cleanup,{}).status_code,200)
        receipt.refresh_from_db();self.assertEqual(receipt.pending_files,[])
        from .attachments import storage
        self.assertFalse(storage().exists(key))

    def test_cross_property_invoice_reference_blocks_purge(self):
        invoice=self.invoice().json()
        other=m.Property.objects.create(agency=self.agency,name='Keep home',address='Keep address',manager=self.pm)
        job=m.MaintenanceRequest.objects.create(property=other,reported_by=self.pm,title='Keep repair',description='Synthetic',category='Plumbing')
        result=self.client.post(reverse('maintenance_invoice',args=[job.pk]),dict(number='INV-CROSS-LINK',amount='500',visibility='shared',due_date='2026-11-15',attachments=docs.document()),HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(result.status_code,201,result.content)
        # Simulate a malformed historical cross-property correction; never delete the other property's invoice.
        m.JobInvoice.objects.filter(pk=result.json()['id']).update(previous_id=invoice['id'])
        self.assertEqual(self.client.get(self.removal('property',self.home.pk)).status_code,400)
        self.assertEqual(m.JobInvoice.objects.count(),2)
        self.assertEqual(m.MaintenanceRequest.objects.count(),2)

    def test_agency_with_staff_customer_membership_requires_access_review(self):
        self.pm.is_staff=True;self.pm.save(update_fields=['is_staff'])
        self.client.force_login(self.ops)
        self.assertEqual(self.client.get(self.removal('agency',self.agency.pk)).status_code,400)
        self.assertTrue(m.Membership.objects.filter(user=self.pm,agency=self.agency).exists())
        self.assertTrue(m.Agency.objects.filter(pk=self.agency.pk).exists())
