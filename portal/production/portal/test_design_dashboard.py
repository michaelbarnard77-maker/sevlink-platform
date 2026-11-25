"""Dashboard counts and role boundaries use the same saved records as the register."""
from django.test import TestCase, override_settings
from django.urls import reverse
from . import test_notifications as fixtures
from . import test_manual_documents as documents
from .models import MaintenanceRequest, Property


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver'])
class DesignDashboardTests(TestCase):
    setUpTestData = classmethod(fixtures.EventWorkflowTests.setUpTestData.__func__)
    setUp = documents.ManualDocumentTests.setUp
    new_job = fixtures.EventWorkflowTests.new_job
    post = fixtures.EventWorkflowTests.post
    invoice = documents.ManualDocumentTests.invoice

    def data(self, user):
        self.client.force_login(user)
        response = self.client.get(reverse('design_dashboard'))
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_counts_and_property_isolation_for_each_role(self):
        other = Property.objects.create(agency=self.agency, manager=self.other_pm, name='Other manager', address='OTHER MANAGER ADDRESS')
        foreign = Property.objects.create(agency=self.foreign_agency, manager=self.foreign, name='Other agency', address='FOREIGN ADDRESS')
        for prop in (other, foreign):
            MaintenanceRequest.objects.create(property=prop, reported_by=self.cotenant, category='Plumbing', title='Private report', description='Private report')
        # Same property, different tenant: no accidental visibility of co-tenant jobs.
        MaintenanceRequest.objects.create(property=self.home, reported_by=self.cotenant, category='Electrical', title='Co-tenant report', description='Private report')
        for user, count in ((self.tenant, 1), (self.pm, 2), (self.admin, 3), (self.ops, 4)):
            data = self.data(user)
            self.assertEqual(data['total'], count)
            self.assertEqual(sum(g['count'] for g in data['groups']), count)
            self.assertEqual(data['active'], count)
            if user != self.ops:
                self.assertNotIn('FOREIGN ADDRESS', str(data))
                self.assertNotIn('invoiced_month', data)
            self.assertNotIn('PRIVATE ACCESS CODE', str(data))
            self.assertNotIn('PRIVATE PHONE', str(data))
        self.assertNotIn('OTHER MANAGER ADDRESS', str(self.data(self.pm)))
        self.assertEqual(self.data(self.tenant)['requests'][0]['job'], str(self.job.pk))

    def test_staff_billing_excludes_internal_supplier_and_void_documents(self):
        self.invoice(number='PUBLIC-CUSTOMER')
        self.invoice(number='PRIVATE-COST', visibility='internal')
        self.assertEqual(self.data(self.ops)['invoiced_month'], '1000')
        self.assertNotIn('invoiced_month', self.data(self.tenant))

    def test_dashboard_is_read_only_and_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('design_dashboard')).status_code, 401)
        self.client.force_login(self.pm)
        self.assertEqual(self.client.post(reverse('design_dashboard')).status_code, 405)
