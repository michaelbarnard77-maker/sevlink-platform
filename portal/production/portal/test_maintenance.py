import json
from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import (Agency, Audit, MaintenanceRequest, MaintenanceStatusEvent,
                     Membership, Property, Tenancy, User)


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False,
                   CSRF_COOKIE_SECURE=False, ALLOWED_HOSTS=['testserver'])
class MaintenanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.agency = Agency.objects.create(name='Agency A', phone='test', area='Test')
        cls.other_agency = Agency.objects.create(name='Agency B', phone='test', area='Test')

        def user(name, role=None, agency=None, **flags):
            u = User.objects.create_user(username=name + '@example.test', email=name + '@example.test', **flags)
            if role:
                Membership.objects.create(user=u, agency=agency or cls.agency, role=role)
            return u

        cls.pm = user('pm', 'pm')
        cls.pm2 = user('pm2', 'pm')
        cls.admin = user('admin', 'admin')
        cls.tenant = user('tenant', 'tenant')
        cls.cotenant = user('cotenant', 'tenant')
        cls.other_pm = user('foreign-pm', 'pm', cls.other_agency)
        cls.other_admin = user('foreign-admin', 'admin', cls.other_agency)
        cls.other_tenant = user('foreign-tenant', 'tenant', cls.other_agency)
        cls.staff = user('staff', is_staff=True)
        cls.superadmin = user('superadmin', is_staff=True, is_superuser=True)
        cls.nonmember = user('nonmember')
        cls.invalid_role = user('unknown', 'unknown')
        cls.home = Property.objects.create(agency=cls.agency, manager=cls.pm, name='Home', address='Test home', access_notes='PRIVATE ACCESS CODE')
        cls.pm2_home = Property.objects.create(agency=cls.agency, manager=cls.pm2, name='PM2 home', address='Other PM home')
        cls.foreign_home = Property.objects.create(agency=cls.other_agency, manager=cls.other_pm, name='Foreign home', address='Foreign address')
        cls.tenancy = Tenancy.objects.create(property=cls.home, user=cls.tenant, name='Tenant', email=cls.tenant.email, phone='test')
        Tenancy.objects.create(property=cls.home, user=cls.cotenant, name='Cotenant', email=cls.cotenant.email, phone='test')
        Tenancy.objects.create(property=cls.pm2_home, user=cls.tenant, name='Tenant', email=cls.tenant.email, phone='test')
        Tenancy.objects.create(property=cls.foreign_home, user=cls.other_tenant, name='Foreign tenant', email=cls.other_tenant.email, phone='test')
        cls.collection = reverse('maintenance_collection')
        cls.context_url = reverse('maintenance_context')

    def login(self, user):
        self.client.force_login(user)

    def report(self, **overrides):
        data = {'property': str(self.home.pk), 'title': 'Leaking tap',
                'description': 'The kitchen tap is dripping.', 'category': 'Plumbing'}
        data.update(overrides)
        return self.client.post(self.collection, json.dumps(data), content_type='application/json')

    def create_report(self):
        self.login(self.tenant)
        response = self.report()
        self.assertEqual(response.status_code, 201, response.content)
        self.detail_url = reverse('maintenance_detail', args=[response.json()['id']])
        return response.json()

    def update(self, status, version=1, **extra):
        return self.client.patch(self.detail_url, json.dumps({'status': status, 'version': version, **extra}), content_type='application/json')

    def test_complete_workflow_survives_logout_and_new_session(self):
        submitted = self.create_report()
        self.assertEqual(submitted['status'], 'awaiting_review')
        self.assertEqual(submitted['version'], 1)
        self.assertEqual(MaintenanceRequest.objects.get().reported_by, self.tenant)
        self.client.logout()
        self.login(self.pm)
        self.assertEqual(self.client.get(self.collection).json()['count'], 1)
        for version, status in enumerate(['reviewed', 'in_progress', 'completed'], start=1):
            response = self.update(status, version)
            self.assertEqual(response.status_code, 200, response.content)
        self.client.logout()
        fresh = Client()
        fresh.force_login(self.tenant)
        result = fresh.get(self.detail_url).json()
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['version'], 4)
        self.assertEqual([e['status'] for e in result['history']], ['awaiting_review', 'reviewed', 'in_progress', 'completed'])
        self.assertEqual(result['allowed_statuses'], [])
        self.assertEqual(MaintenanceStatusEvent.objects.count(), 4)
        self.assertEqual(Audit.objects.filter(object_id=submitted['id']).count(), 4)

    def test_other_agencies_cannot_list_read_update_or_report_for_property(self):
        self.create_report()
        for user in [self.other_pm, self.other_admin, self.other_tenant]:
            self.login(user)
            self.assertEqual(self.client.get(self.collection).json()['count'], 0)
            self.assertEqual(self.client.get(self.detail_url).status_code, 404)
            self.assertEqual(self.update('reviewed').status_code, 404)
        self.assertEqual(self.report().status_code, 400)
        self.assertEqual(MaintenanceRequest.objects.count(), 1)
        self.assertEqual(MaintenanceRequest.objects.get().status, 'awaiting_review')

    def test_other_pm_and_cotenant_cannot_read_or_update(self):
        self.create_report()
        for user in [self.pm2, self.cotenant]:
            self.login(user)
            self.assertEqual(self.client.get(self.collection).json()['count'], 0)
            self.assertEqual(self.client.get(self.detail_url).status_code, 404)
            self.assertEqual(self.update('reviewed').status_code, 404)

    def test_tenant_cannot_change_status_or_forge_privileged_fields(self):
        self.create_report()
        self.assertEqual(self.update('reviewed').status_code, 403)
        for field in ['agency', 'reported_by', 'status', 'internal_notes', 'role', 'subcontractor']:
            self.assertEqual(self.report(**{field: 'forged'}).status_code, 400)
        self.assertEqual(MaintenanceRequest.objects.count(), 1)

    def test_superadmin_views_all_agencies_but_staff_is_not_superadmin(self):
        first = self.create_report()
        self.login(self.other_tenant)
        self.assertEqual(self.report(property=str(self.foreign_home.pk)).status_code, 201)
        self.login(self.superadmin)
        self.assertEqual(self.client.get(self.collection).json()['count'], 2)
        self.assertEqual(self.client.get(self.detail_url).json()['id'], first['id'])
        self.assertEqual(self.update('reviewed').status_code, 200)
        self.login(self.staff)
        for url in [self.collection, self.detail_url, self.context_url, reverse('maintenance_workspace')]:
            self.assertEqual(self.client.get(url).status_code, 403)
        # Membership does not prevent an explicitly designated superadmin from global visibility.
        Membership.objects.create(user=self.superadmin, agency=self.agency, role='admin')
        self.login(self.superadmin)
        self.assertEqual(self.client.get(self.collection).json()['count'], 2)

    def test_agency_admin_can_review_and_other_pm_can_review_only_own_portfolio(self):
        self.create_report()
        self.login(self.admin)
        self.assertEqual(self.update('reviewed').status_code, 200)
        self.login(self.tenant)
        created = self.report(property=str(self.pm2_home.pk))
        self.assertEqual(created.status_code, 201)
        self.detail_url = reverse('maintenance_detail', args=[created.json()['id']])
        self.login(self.pm2)
        self.assertEqual(self.update('reviewed').status_code, 200)
        self.login(self.pm)
        self.assertEqual(self.client.get(self.detail_url).status_code, 404)

    def test_inactive_or_removed_tenancy_revokes_request_access(self):
        self.create_report()
        self.tenancy.active = False
        self.tenancy.save()
        self.assertEqual(self.client.get(self.detail_url).status_code, 404)
        self.assertEqual(self.client.get(self.collection).json()['count'], 0)
        self.assertEqual(self.report().status_code, 400)

    def test_ownership_is_derived_from_active_tenancy_and_agency(self):
        self.login(self.tenant)
        self.assertEqual(self.report(property=str(self.foreign_home.pk)).status_code, 400)
        # Even an inconsistent cross-agency tenancy cannot authorize access.
        Tenancy.objects.create(property=self.foreign_home, user=self.tenant, name='Bad link', email=self.tenant.email, phone='test')
        self.assertEqual(self.report(property=str(self.foreign_home.pk)).status_code, 400)
        self.assertNotIn(str(self.foreign_home.pk), json.dumps(self.client.get(self.context_url).json()))

    def test_private_fields_and_staff_identities_are_not_serialized(self):
        submitted = self.create_report()
        MaintenanceRequest.objects.update(internal_notes='PRIVATE SUBCONTRACTOR NAME; COST AND INTERNAL NOTES')
        for user in [self.tenant, self.pm, self.admin, self.superadmin]:
            self.login(user)
            detail = self.client.get(self.detail_url)
            data = detail.json()
            self.assertEqual(set(data), {'id', 'reference', 'property', 'title', 'description', 'category',
                                        'status', 'status_label', 'version', 'created_at', 'updated_at', 'allowed_statuses', 'history'})
            for url in [self.detail_url, self.collection, self.context_url]:
                content = self.client.get(url).content.decode()
                for secret in ['PRIVATE SUBCONTRACTOR', 'PRIVATE ACCESS CODE', 'internal_notes', 'reported_by', 'actor']:
                    self.assertNotIn(secret, content)
                if url != self.context_url:
                    self.assertNotIn(self.tenant.email, content)
            self.assertEqual(set(data['history'][0]), {'status', 'label', 'at'})
        self.assertEqual(submitted['property']['address'], 'Test home')

    def test_invalid_input_unknown_fields_and_malformed_json(self):
        self.login(self.tenant)
        for overrides in [{'title': ''}, {'description': '   '}, {'title': 'x' * 181},
                          {'description': 'x' * 2501}, {'category': 'Unknown'}, {'property': 'invalid-uuid'}, {'property': None}, {'title': {'nested': 'object'}}, {'description': 12}]:
            self.assertEqual(self.report(**overrides).status_code, 400, overrides)
        for body in ['{', 'null', '[]', '"text"', '{"status": true}']:
            self.assertEqual(self.client.post(self.collection, body, content_type='application/json').status_code, 400)
        self.assertEqual(self.client.post(self.collection, '{}', content_type='text/plain').status_code, 400)
        self.assertEqual(self.client.post(self.collection, ' ' * 17000, content_type='application/json').status_code, 400)
        self.assertEqual(MaintenanceRequest.objects.count(), 0)

    def test_invalid_repeated_and_stale_status_updates_are_rejected(self):
        self.create_report()
        self.login(self.pm)
        for status in ['completed', 'awaiting_review', 'made-up']:
            self.assertEqual(self.update(status).status_code, 400)
        for version in [True, '1', None]:
            self.assertEqual(self.update('reviewed', version).status_code, 400)
        self.assertEqual(self.update('reviewed', internal_notes='forged').status_code, 400)
        self.assertEqual(self.update('reviewed').status_code, 200)
        self.assertEqual(self.update('in_progress', 1).status_code, 409)
        self.assertEqual(self.update('reviewed', 2).status_code, 400)
        self.assertEqual(MaintenanceStatusEvent.objects.count(), 2)
        self.assertEqual(self.update('cancelled', 2).status_code, 200)
        self.assertEqual(self.update('reviewed', 3).status_code, 400)

    def test_csrf_required_for_submission_and_status_update(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.tenant)
        data = {'property': str(self.home.pk), 'title': 'Tap', 'description': 'Leaking', 'category': 'Plumbing'}
        self.assertEqual(strict.post(self.collection, json.dumps(data), content_type='application/json').status_code, 403)
        context = strict.get(self.context_url)
        self.assertEqual(context.status_code, 200)
        token = strict.cookies['csrftoken'].value
        submitted = strict.post(self.collection, json.dumps(data), content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(submitted.status_code, 201)
        self.detail_url = reverse('maintenance_detail', args=[submitted.json()['id']])
        strict.force_login(self.pm)
        self.assertEqual(strict.patch(self.detail_url, '{"status":"reviewed","version":1}', content_type='application/json').status_code, 403)
        self.assertEqual(strict.patch(self.detail_url, '{"status":"reviewed","version":1}', content_type='application/json', HTTP_X_CSRFTOKEN=token).status_code, 200)

    def test_anonymous_inactive_nonmember_and_invalid_role(self):
        for url in [self.collection, self.context_url]:
            self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.get(reverse('maintenance_workspace')).status_code, 302)
        for user in [self.nonmember, self.invalid_role]:
            self.login(user)
            self.assertEqual(self.client.get(self.collection).status_code, 403)
        self.tenant.is_active = False
        self.tenant.save()
        self.login(self.tenant)
        self.assertEqual(self.client.get(self.collection).status_code, 401)

    def test_managers_cannot_create_tenant_reports_and_methods_are_restricted(self):
        self.create_report()
        for user in [self.pm, self.admin, self.superadmin]:
            self.login(user)
            self.assertEqual(self.report().status_code, 403)
        self.assertEqual(self.client.delete(self.detail_url).status_code, 405)
        self.assertEqual(self.client.post(self.detail_url, '{}', content_type='application/json').status_code, 405)
        self.assertEqual(self.client.patch(self.collection, '{}', content_type='application/json').status_code, 405)
        self.assertEqual(self.client.post(self.context_url).status_code, 405)
        self.assertEqual(MaintenanceRequest.objects.get().status, 'awaiting_review')

    def test_paginated_results_and_invalid_page(self):
        self.create_report()
        MaintenanceRequest.objects.bulk_create([MaintenanceRequest(property=self.home, reported_by=self.tenant,
            title='Repair ' + str(i), description='Test', category='Plumbing') for i in range(50)])
        data = self.client.get(self.collection).json()
        self.assertEqual((data['count'], len(data['results']), data['next']), (51, 50, 2))
        second = self.client.get(self.collection, {'page': 2}).json()
        self.assertEqual(len(second['results']), 1)
        self.assertIsNone(second['next'])
        self.assertFalse({j['id'] for j in data['results']} & {j['id'] for j in second['results']})
        for page in ['bad', 0, -1, 1000001]:
            self.assertEqual(self.client.get(self.collection, {'page': page}).status_code, 400)

    def test_submission_and_status_audit_are_atomic(self):
        self.login(self.tenant)
        with patch('portal.maintenance.Audit.objects.create', side_effect=RuntimeError('test rollback')):
            with self.assertRaises(RuntimeError):
                self.report()
        self.assertEqual(MaintenanceRequest.objects.count(), 0)
        self.assertEqual(MaintenanceStatusEvent.objects.count(), 0)
        self.create_report()
        self.login(self.pm)
        with patch('portal.maintenance.Audit.objects.create', side_effect=RuntimeError('test rollback')):
            with self.assertRaises(RuntimeError):
                self.update('reviewed')
        self.assertEqual(MaintenanceRequest.objects.get().status, 'awaiting_review')
        self.assertEqual(MaintenanceStatusEvent.objects.count(), 1)

    def test_status_constraint_and_parent_records_are_protected(self):
        self.create_report()
        with self.assertRaises(IntegrityError), transaction.atomic():
            MaintenanceRequest.objects.update(status='invalid')
        from django.db.models.deletion import ProtectedError
        with self.assertRaises(ProtectedError):
            self.home.delete()

    def test_workspace_uses_existing_styles_without_demo_scripts(self):
        self.login(self.tenant)
        response = self.client.get(reverse('maintenance_workspace'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'maintenance.js')
        self.assertContains(response, 'professional-polish.css')
        self.assertContains(response, 'maintenance-ui/')
        for sample in ['app.js', 'job-cancellation.js', 'Michael Barnard', 'DEMO WORKSPACE', 'Preview role']:
            self.assertNotContains(response, sample)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn('no-store', self.client.get(self.collection)['Cache-Control'])
