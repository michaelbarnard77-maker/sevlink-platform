"""Optional real-browser workflow test; uses Django's isolated temporary test DB."""
import json
import base64
from .test_attachments import document
import os
from pathlib import Path
import subprocess
import tempfile
from datetime import timedelta
from unittest import skipUnless

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from django.utils import timezone

from .models import Agency, Membership, Property, Tenancy, User, MaintenanceRequest, JobQuotation, JobComment, OperationsNotification, JobInvoice, InvoicePayment, InvoiceRefund, QuoteApprovalReplacement


@skipUnless(os.environ.get('SEVLINK_BROWSER_TESTS') == '1', 'Set SEVLINK_BROWSER_TESTS=1 with Node Playwright installed.')
@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class MaintenanceBrowserTests(StaticLiveServerTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='sevlink-browser-private-')
        self.addCleanup(directory.cleanup)
        aliases = {**settings.STORAGES, 'maintenance_private': {
            'BACKEND': 'portal.attachment_storage.PrivateAttachmentStorage', 'OPTIONS': {'location': directory.name}}}
        override = override_settings(PRIVATE_ATTACHMENT_ROOT=directory.name, STORAGES=aliases)
        override.enable()
        self.addCleanup(override.disable)

    def test_tenant_submission_manager_update_and_relogin(self):
        agency = Agency.objects.create(name='Browser test agency', phone='test', area='Test')
        sessions = {}
        for role in ['tenant', 'pm', 'superadmin']:
            user = User.objects.create_user(username=role + '@example.test', email=role + '@example.test', first_name=role,
                                            is_staff=role == 'superadmin', is_superuser=role == 'superadmin')
            if role != 'superadmin':
                Membership.objects.create(user=user, agency=agency, role=role)
            client = Client()
            client.force_login(user)
            sessions[role] = client.cookies[settings.SESSION_COOKIE_NAME].value
        foreign_agency = Agency.objects.create(name='Foreign browser agency', phone='test', area='Test')
        foreign_pm = User.objects.create_user(username='foreign@example.test', email='foreign@example.test')
        Membership.objects.create(user=foreign_pm, agency=foreign_agency, role='pm')
        foreign_client = Client(); foreign_client.force_login(foreign_pm)
        sessions['foreign'] = foreign_client.cookies[settings.SESSION_COOKIE_NAME].value
        prop = Property.objects.create(agency=agency, manager=User.objects.get(first_name='pm'), name='Browser home', address='12 Test Road')
        tenant = User.objects.get(first_name='tenant')
        fresh_client = Client()
        fresh_client.force_login(tenant)
        sessions['tenantAgain'] = fresh_client.cookies[settings.SESSION_COOKIE_NAME].value
        Tenancy.objects.create(property=prop, user=tenant, name='Test tenant', email=tenant.email, phone='test')
        script = Path(settings.BASE_DIR).parents[1] / 'scripts' / 'test-maintenance-browser.cjs'
        result = subprocess.run(['node', str(script)], input=json.dumps({'url': self.live_server_url, 'sessions': sessions, 'pdf':base64.b64encode(document().read()).decode(), 'today':timezone.localdate().isoformat()}),
                                text=True, capture_output=True, timeout=150)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS', result.stdout)
        self.assertEqual(MaintenanceRequest.objects.get().status, 'reviewed')
        self.assertEqual(MaintenanceRequest.objects.get().attachments.filter(purpose='general').count(), 2)
        self.assertEqual(JobQuotation.objects.filter(status='approved').count(),2)
        self.assertEqual(QuoteApprovalReplacement.objects.count(),1)
        self.assertEqual(JobComment.objects.filter(visibility='shared').count(), 2)
        self.assertEqual(JobComment.objects.filter(visibility='internal').count(), 1)
        self.assertEqual(OperationsNotification.objects.count(), 5)
        self.assertEqual(JobInvoice.objects.get(previous__isnull=True).document_status,'void')
        self.assertTrue(JobInvoice.objects.get(previous__isnull=False).reconciliation_required)
        self.assertEqual(InvoicePayment.objects.get().amount,250)
        self.assertEqual(InvoiceRefund.objects.get().amount,100)

    def test_operations_multi_region_assignments(self):
        from .test_regions import fixtures
        from .models import JobAssignment, Subcontractor
        fixtures(self)
        from .models import TradeCategory
        TradeCategory.objects.get_or_create(name='Plumbing')  # LiveServer DB is flushed between test classes.
        sessions = {}
        for role, user in [('ops', self.ops), ('pm', self.pm)]:
            client = Client(); client.force_login(user)
            sessions[role] = client.cookies[settings.SESSION_COOKIE_NAME].value
        script = Path(settings.BASE_DIR).parents[1] / 'scripts' / 'test-regions-browser.cjs'
        monday=timezone.localdate()+timedelta(days=7)
        monday+=timedelta(days=(0-monday.weekday())%7)
        result = subprocess.run(['node', str(script)], input=json.dumps({
            'url': self.live_server_url, 'sessions': sessions,
            'pdf':base64.b64encode(document().read()).decode(), 'expires':str(timezone.localdate()+timedelta(days=15)),
            'appointmentDay':str(monday), 'unavailableDay':str(monday+timedelta(days=1)),
            'ids': {'wc':self.wc.pk, 'cape':self.cape.pk, 'joburg':self.joburg.pk,
                    'job':str(self.cape_job.pk), 'gpjob':str(self.job.pk), 'partner':str(self.partner.pk)}}),
            text=True, capture_output=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS', result.stdout)
        self.assertEqual(JobAssignment.objects.count(),2)
        self.assertEqual(JobAssignment.objects.first().request_id,self.cape_job.pk)
        self.assertEqual(JobAssignment.objects.first().team.name,'Team A')
        from .models import TeamAppointment, ComplianceDocument
        self.assertEqual(TeamAppointment.objects.get().team.name,'Team A')
        self.assertEqual(ComplianceDocument.objects.count(),1)
        partner = Subcontractor.objects.get(name='Browser dual-region partner')
        self.assertEqual(set(partner.cities.values_list('pk', flat=True)), {self.cape.pk,self.joburg.pk})
