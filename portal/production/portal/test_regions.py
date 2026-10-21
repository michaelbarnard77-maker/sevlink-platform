"""Multi-region matching, private Operations access and additive data preservation."""
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless

from django.core.exceptions import ValidationError
from django.db import connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from .models import (Agency, City, JobActivity, JobAssignment, MaintenanceRequest,
                     Membership, Property, Province, Subcontractor, Suburb, Tenancy, User)
from .regions import eligible

SETTINGS = dict(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False,
                CSRF_COOKIE_SECURE=False, ALLOWED_HOSTS=['testserver'])


def fixtures(cls):
    cls.ops = User.objects.create_user(username='region-ops', email='region-ops@example.test', is_superuser=True)
    cls.gp, _ = Province.objects.get_or_create(code='GP', defaults={'name': 'Gauteng'})
    cls.wc, _ = Province.objects.get_or_create(code='WC', defaults={'name': 'Western Cape'})
    cls.joburg, _ = City.objects.get_or_create(province=cls.gp, name='Johannesburg')
    cls.cape, _ = City.objects.get_or_create(province=cls.wc, name='Cape Town')
    cls.sea = Suburb.objects.create(city=cls.cape, name='Sea Point')
    cls.gardens = Suburb.objects.create(city=cls.cape, name='Gardens')
    cls.agency = Agency.objects.create(name='Regional agency', phone='test', area='Gauteng')
    cls.other = Agency.objects.create(name='Other agency', phone='test', area='Cape Town')
    cls.pm = User.objects.create_user(username='region-pm', email='region-pm@example.test')
    Membership.objects.create(user=cls.pm, agency=cls.agency, role='pm')
    cls.tenant = User.objects.create_user(username='region-tenant', email='region-tenant@example.test')
    Membership.objects.create(user=cls.tenant, agency=cls.agency, role='tenant')
    cls.home = Property.objects.create(agency=cls.agency, manager=cls.pm, name='Gauteng home', address='Original Gauteng address', city=cls.joburg)
    cls.coastal = Property.objects.create(agency=cls.other, name='Cape home', address='Original Cape address', city=cls.cape, suburb=cls.sea)
    cls.legacy = Property.objects.create(agency=cls.agency, name='Legacy', address='Existing Gauteng free text')
    Tenancy.objects.create(property=cls.home, user=cls.tenant, name='Test tenant', email=cls.tenant.email, phone='test')
    cls.job = MaintenanceRequest.objects.create(property=cls.home, reported_by=cls.tenant, title='GP repair', description='test', category='Plumbing')
    cls.cape_job = MaintenanceRequest.objects.create(property=cls.coastal, reported_by=cls.tenant, title='Cape repair', description='test', category='Plumbing')
    from .models import SchedulingArrangement
    for job in (cls.job,cls.cape_job):SchedulingArrangement.objects.create(request=job,actor=cls.ops,reason='Synthetic reviewed scheduling terms')
    cls.partner = Subcontractor.objects.create(name='PRIVATE multi-region partner', created_by=cls.ops)
    cls.partner.cities.add(cls.joburg, cls.cape)
    cls.local = Subcontractor.objects.create(name='PRIVATE Sea Point only', created_by=cls.ops)
    cls.local.suburbs.add(cls.sea)
    cls.inland = Subcontractor.objects.create(name='PRIVATE Gauteng only', created_by=cls.ops)
    cls.inland.provinces.add(cls.gp)
    cls.inactive = Subcontractor.objects.create(name='PRIVATE inactive', created_by=cls.ops, active=False)
    cls.inactive.provinces.add(cls.gp, cls.wc)


def assign(client, job, contractor, version=1, key=None):
    return client.post(reverse('operations_assignments', args=[job.pk]), json.dumps({
        'subcontractor': str(contractor.pk), 'version': version,
        'submission_key': str(key or uuid.uuid4())}), content_type='application/json')


@override_settings(**SETTINGS)
class RegionalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        fixtures(cls)

    def setUp(self):
        self.client.force_login(self.ops)

    def post(self, name, data, args=()):
        return self.client.post(reverse(name, args=args), json.dumps(data), content_type='application/json')

    def test_multi_region_partner_matches_both_and_suburb_is_precise(self):
        self.assertEqual(set(eligible(self.home)), {self.partner, self.inland})
        self.assertEqual(set(eligible(self.coastal)), {self.partner, self.local})
        self.coastal.suburb = self.gardens; self.coastal.save()
        self.assertEqual(set(eligible(self.coastal)), {self.partner})
        self.coastal.suburb = None; self.coastal.save()
        self.assertEqual(set(eligible(self.coastal)), {self.partner})
        self.assertFalse(eligible(self.legacy).exists())

    def test_assignment_succeeds_in_both_regions_and_preserves_private_history(self):
        for job in (self.job, self.cape_job):
            response = assign(self.client, job, self.partner)
            self.assertEqual(response.status_code, 201, response.content)
            job.refresh_from_db(); self.assertEqual(job.status, 'awaiting_review')
            self.assertEqual(job.version, 2)
        self.assertEqual(JobAssignment.objects.count(), 2)
        self.assertEqual(JobActivity.objects.filter(kind='job_assigned', visibility='internal').count(), 2)
        from .models import OperationsNotification
        self.assertEqual(OperationsNotification.objects.count(), 0)
        assignment = JobAssignment.objects.get(request=self.cape_job)
        self.assertEqual((assignment.city, assignment.suburb), (self.cape, self.sea))
        with self.assertRaises(ValidationError): assignment.delete()
        with self.assertRaises(ValidationError): JobAssignment.objects.all().update(city=self.joburg)

    def test_candidate_endpoint_excludes_outside_area_and_inactive(self):
        data = self.client.get(reverse('operations_assignments', args=[self.cape_job.pk])).json()
        self.assertEqual({c['id'] for c in data['subcontractors']}, {str(self.partner.pk), str(self.local.pk)})
        self.assertFalse(data['location_required'])
        self.assertEqual(assign(self.client, self.cape_job, self.inland).status_code, 400)
        self.assertEqual(assign(self.client, self.job, self.inactive).status_code, 400)
        self.assertEqual(JobAssignment.objects.count(), 0)

    def test_idempotency_duplicate_and_stale_decisions(self):
        key = uuid.uuid4()
        self.assertEqual(assign(self.client, self.job, self.partner, key=key).status_code, 201)
        self.assertEqual(assign(self.client, self.job, self.partner, key=key).status_code, 200)
        self.assertEqual(assign(self.client, self.job, self.inland, key=key).status_code, 409)
        self.assertEqual(assign(self.client, self.job, self.inland, version=1).status_code, 409)
        self.assertEqual(assign(self.client, self.job, self.partner, version=2).status_code, 409)
        self.assertEqual(JobAssignment.objects.count(), 1)
        self.assertEqual(assign(self.client, self.job, self.inland, version=2).status_code, 201)
        self.assertEqual(JobAssignment.objects.count(), 2)

    def test_closed_jobs_and_unmapped_properties_cannot_be_assigned(self):
        for status in ('completed', 'cancelled'):
            self.job.status = status; self.job.save()
            self.assertEqual(assign(self.client, self.job, self.partner).status_code, 409)
        job = MaintenanceRequest.objects.create(property=self.legacy, reported_by=self.tenant, title='Legacy', description='Test', category='Plumbing')
        self.assertEqual(assign(self.client, job, self.partner).status_code, 400)
        data = self.client.get(reverse('operations_assignments', args=[job.pk])).json()
        self.assertTrue(data['location_required']); self.assertEqual(data['subcontractors'], [])

    def test_filter_contractors_properties_and_jobs_by_province_city_suburb(self):
        for params in ({'province': self.wc.pk}, {'city': self.cape.pk}, {'suburb': self.sea.pk}):
            response = self.client.get(reverse('operations_regions'), params)
            self.assertEqual(response.status_code, 200, response.content)
            data = response.json()
            self.assertEqual([p['id'] for p in data['properties']['results']], [str(self.coastal.pk)])
            self.assertEqual([j['id'] for j in data['jobs']['results']], [str(self.cape_job.pk)])
            self.assertIn(str(self.partner.pk), [c['id'] for c in data['subcontractors']['results']])
            self.assertNotIn(str(self.inland.pk), [c['id'] for c in data['subcontractors']['results']])
        data = self.client.get(reverse('operations_regions')).json()
        self.assertEqual(data['properties']['count'], 3)
        self.assertEqual(data['jobs']['count'], 2)
        self.assertEqual(self.client.get(reverse('operations_regions'), {'province': self.gp.pk, 'city': self.cape.pk}).status_code, 400)
        self.assertEqual(self.client.get(reverse('operations_regions'), {'page': 0}).status_code, 400)

    def test_map_location_validates_hierarchy_and_preserves_address(self):
        response = self.post('operations_property_location', {'city': self.cape.pk, 'suburb': self.sea.pk}, [self.legacy.pk])
        self.assertEqual(response.status_code, 200, response.content)
        self.legacy.refresh_from_db()
        self.assertEqual(self.legacy.address, 'Existing Gauteng free text')
        self.assertEqual(self.legacy.city, self.cape)
        self.assertEqual(self.post('operations_property_location', {'city': self.joburg.pk, 'suburb': self.sea.pk}, [self.home.pk]).status_code, 400)
        self.home.suburb = self.sea
        with self.assertRaises(ValidationError): self.home.save()

    def test_operations_can_register_and_change_multi_area_coverage(self):
        body = {'name': 'New partner', 'active': True, 'provinces': [self.gp.pk], 'cities': [self.cape.pk], 'suburbs': [self.sea.pk]}
        response = self.post('operations_subcontractor', body)
        self.assertEqual(response.status_code, 200, response.content)
        item = Subcontractor.objects.get(pk=response.json()['id'])
        self.assertIn(item, eligible(self.home)); self.assertIn(item, eligible(self.coastal))
        body.update(id=str(item.pk), active=False)
        self.assertEqual(self.post('operations_subcontractor', body).status_code, 200)
        self.assertNotIn(item, eligible(self.coastal))
        for changes in ({'cities': [999999]}, {'cities': [True]}, {'active': 'yes'}, {'name': ''}):
            self.assertEqual(self.post('operations_subcontractor', {**body, **changes}).status_code, 400)

    def test_additional_province_city_and_suburb_need_no_code_change(self):
        province, _ = Province.objects.get_or_create(code='EC', defaults={'name': 'Eastern Cape'})
        response = self.post('operations_regions', {'kind': 'city', 'name': 'Gqeberha', 'province': province.pk})
        self.assertEqual(response.status_code, 201, response.content)
        city = City.objects.get(pk=response.json()['id'])
        response = self.post('operations_regions', {'kind': 'suburb', 'name': 'Summerstrand', 'city': city.pk})
        self.assertEqual(response.status_code, 201)
        self.partner.cities.add(city)
        self.legacy.city = city; self.legacy.save()
        self.assertIn(self.partner, eligible(self.legacy))
        self.assertEqual(self.post('operations_regions', {'kind': 'city', 'name': 'gqeberha', 'province': province.pk}).status_code, 400)

    def test_private_apis_deny_all_non_operations_roles_and_foreign_agencies(self):
        foreign = User.objects.create_user(username='region-foreign', email='region-foreign@example.test')
        Membership.objects.create(user=foreign, agency=self.other, role='admin')
        staff = User.objects.create_user(username='region-staff', email='region-staff@example.test', is_staff=True)
        urls = [reverse('operations_regions'), reverse('operations_assignments', args=[self.job.pk])]
        for user in (self.tenant, self.pm, foreign, staff):
            self.client.force_login(user)
            for url in urls:
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url, '{}', content_type='application/json').status_code, 403)
            self.assertEqual(self.post('operations_subcontractor', {}).status_code, 403)
            self.assertEqual(self.post('operations_property_location', {'city': self.cape.pk}, [self.home.pk]).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(urls[0]).status_code, 401)

    def test_assignment_identities_never_leak_to_pm_tenant_or_foreign_api(self):
        self.assertEqual(assign(self.client, self.job, self.partner).status_code, 201)
        for user in (self.pm, self.tenant):
            self.client.force_login(user)
            for url in (reverse('maintenance_detail', args=[self.job.pk]), reverse('maintenance_collection')):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                text = response.content.decode()
                for secret in (self.partner.name, str(self.partner.pk), 'subcontractor_id', 'job_assigned'):
                    self.assertNotIn(secret, text)
            self.assertEqual(self.client.get(reverse('maintenance_detail', args=[self.cape_job.pk])).status_code, 404)

    def test_csrf_and_invalid_assignment_values(self):
        client = Client(enforce_csrf_checks=True); client.force_login(self.ops)
        self.assertEqual(assign(client, self.job, self.partner).status_code, 403)
        for body in ({'subcontractor': str(self.partner.pk), 'version': True, 'submission_key': str(uuid.uuid4())},
                     {'subcontractor': None, 'version': 1, 'submission_key': None}):
            self.assertEqual(self.post('operations_assignments', body, [self.job.pk]).status_code, 400)


@override_settings(**SETTINGS)
@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL locking test')
class RegionalConcurrencyTests(TransactionTestCase):
    def setUp(self): fixtures(self)

    def test_simultaneous_assignments_allow_only_one_current_version(self):
        def action(contractor_id):
            try:
                client = Client(); client.force_login(User.objects.get(pk=self.ops.pk))
                return assign(client, self.job, Subcontractor.objects.get(pk=contractor_id)).status_code
            finally:
                connections.close_all()
                for alias in connections: self.assertIsNone(connections[alias].connection)
        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(action, [self.partner.pk, self.inland.pk]))
        self.assertEqual(sorted(statuses), [201, 409])
        self.assertEqual(JobAssignment.objects.count(), 1)
        self.job.refresh_from_db(); self.assertEqual(self.job.version, 2)


class RegionalMigrationTests(TransactionTestCase):
    def test_preserves_gauteng_records_without_guessing_coordinates(self):
        old = [('portal', '0013_reserve_historical_document_numbers')]
        new = [('portal', '0026_jobactionrequest_job_active_action_unique')]
        try:
            MigrationExecutor(connection).migrate(old)
            apps = MigrationExecutor(connection).loader.project_state(old).apps
            agency = apps.get_model('portal', 'Agency').objects.create(name='Historical GP', phone='test', area='Gauteng')
            prop = apps.get_model('portal', 'Property').objects.create(agency=agency, name='Existing GP', address='Meyerton, Gauteng')
            MigrationExecutor(connection).migrate(new)
            apps = MigrationExecutor(connection).loader.project_state(new).apps
            actual = apps.get_model('portal', 'Property').objects.get(pk=prop.pk)
            self.assertEqual(actual.address, 'Meyerton, Gauteng')
            self.assertIsNone(actual.city_id); self.assertIsNone(actual.suburb_id)
            self.assertEqual(apps.get_model('portal', 'Agency').objects.get(pk=agency.pk).area, 'Gauteng')
            self.assertEqual(apps.get_model('portal', 'Province').objects.count(), 9)
            self.assertTrue(apps.get_model('portal', 'City').objects.filter(name='Cape Town', province__code='WC').exists())
            self.assertTrue(apps.get_model('portal', 'City').objects.filter(name='Meyerton', province__code='GP').exists())
        finally:
            MigrationExecutor(connection).migrate(new)
