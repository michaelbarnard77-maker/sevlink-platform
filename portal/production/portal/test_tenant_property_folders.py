from django.test import TestCase,override_settings
from django.urls import reverse
from django.db import connection
from django.test.utils import CaptureQueriesContext
from . import test_notifications as fixtures
from .models import Property,Tenancy

@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False,ALLOWED_HOSTS=['testserver'])
class TenantPropertyFolderTests(TestCase):
    setUpTestData=classmethod(fixtures.EventWorkflowTests.setUpTestData.__func__)

    def page(self,user):
        self.client.force_login(user)
        return self.client.get(reverse('customer_portal_section',args=['tenants']))

    def test_admin_groups_by_property_id_including_empty_properties_and_pending_invites(self):
        other=Property.objects.create(agency=self.agency,manager=self.other_pm,name='Another unit',address=self.home.address)
        empty=Property.objects.create(agency=self.agency,manager=self.admin,name='Empty property',address='Unoccupied example')
        pending=Tenancy.objects.create(property=other,name='Pending tenant',email='pending@example.test',active=True)
        Tenancy.objects.create(property=other,name='Former tenant',email='former@example.test',active=False)
        result=self.page(self.admin).json()
        groups={p['id']:p for p in result['properties']}
        self.assertEqual(set(groups),{str(self.home.pk),str(other.pk),str(empty.pk)})
        self.assertEqual(groups[str(empty.pk)]['tenants'],[])
        self.assertEqual([t['id'] for t in groups[str(other.pk)]['tenants']],[str(pending.pk)])
        self.assertFalse(groups[str(other.pk)]['tenants'][0]['linked'])
        self.assertEqual(groups[str(other.pk)]['invite_url'],reverse('invite_tenant',args=[other.pk]))
        self.assertNotIn('Former tenant',str(result))
        self.assertEqual({t['id'] for t in result['tenants']},{t['id'] for p in groups.values() for t in p['tenants']})

    def test_pm_sees_only_assigned_properties_and_tenants_not_another_agency_or_pm(self):
        other=Property.objects.create(agency=self.agency,manager=self.other_pm,name='Other PM property',address='OTHER PM PROPERTY')
        foreign=Property.objects.create(agency=self.foreign_agency,manager=self.foreign,name='Foreign property',address='FOREIGN PROPERTY')
        for prop in (other,foreign):Tenancy.objects.create(property=prop,name=prop.name,email=str(prop.pk)+'@example.test')
        response=self.page(self.pm);self.assertEqual(response.status_code,200)
        result=response.json();self.assertEqual([p['id'] for p in result['properties']],[str(self.home.pk)])
        self.assertNotIn('OTHER PM PROPERTY',response.content.decode());self.assertNotIn('FOREIGN PROPERTY',response.content.decode())
        self.assertEqual(self.page(self.tenant).status_code,403)

    def test_hundred_property_folder_list_uses_batched_tenant_queries(self):
        for n in range(100):
            prop=Property.objects.create(agency=self.agency,manager=self.pm,name=f'Example {n}',address=f'{n} Example Lane')
            Tenancy.objects.create(property=prop,name=f'Tenant {n}',email=f'tenant{n}@example.test')
        self.client.force_login(self.admin)
        with CaptureQueriesContext(connection) as queries:
            response=self.client.get(reverse('customer_portal_section',args=['tenants']))
        self.assertEqual(response.status_code,200);self.assertEqual(len(response.json()['properties']),101)
        self.assertLess(len(queries),20)
