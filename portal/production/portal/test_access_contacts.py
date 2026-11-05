from django.test import TestCase, override_settings
from django.urls import reverse
from . import test_maintenance as fixtures
from .models import MaintenanceRequest, Tenancy


@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False,ALLOWED_HOSTS=['testserver'])
class AccessContactTests(TestCase):
    setUpTestData=classmethod(fixtures.MaintenanceTests.setUpTestData.__func__)

    def setUp(self):
        self.job=MaintenanceRequest.objects.create(property=self.home,reported_by=self.tenant,title='Access test',description='Contact check',category='Plumbing',job_type='quoted',status='reviewed',access_responsibility='sevlink')
        self.tenancy.phone='082 000 0000';self.tenancy.save(update_fields=['phone'])
        Tenancy.objects.create(property=self.home,name='Inactive tenant',email='inactive@example.test',phone='INACTIVE PRIVATE',active=False)
        self.url=reverse('maintenance_detail',args=[self.job.pk])

    def test_sevlink_contact_is_active_and_linked_to_this_address(self):
        self.client.force_login(self.superadmin)
        result=self.client.get(self.url);self.assertEqual(result.status_code,200)
        contacts=result.json()['workflow']['access_contacts']
        self.assertTrue(any(c['phone']=='082 000 0000' for c in contacts))
        self.assertTrue(all(c['address']==self.home.address for c in contacts))
        self.assertNotIn('INACTIVE PRIVATE',str(contacts))
        self.assertNotIn(self.foreign_home.address,str(contacts))

    def test_pm_arranged_access_does_not_serialize_contact_section(self):
        self.job.access_responsibility='pm';self.job.save(update_fields=['access_responsibility'])
        self.client.force_login(self.superadmin)
        self.assertNotIn('access_contacts',self.client.get(self.url).json()['workflow'])

    def test_tenant_pm_and_other_agency_do_not_receive_sevlink_contact_list(self):
        for user in [self.tenant,self.pm]:
            self.client.force_login(user);self.assertNotIn('access_contacts',self.client.get(self.url).json()['workflow'])
        self.client.force_login(self.other_pm)
        self.assertEqual(self.client.get(self.url).status_code,404)
