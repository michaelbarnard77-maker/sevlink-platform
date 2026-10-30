"""Synthetic CK-sized portfolio checks; not a production load certification."""
from django.test import TestCase, override_settings
from .models import Agency, User, Membership, Property, MaintenanceRequest, Tenancy

@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False)
class PilotPortfolioTests(TestCase):
    def test_hundred_properties_paginated_jobs_and_two_manager_isolation(self):
        agency=Agency.objects.create(name='Synthetic pilot portfolio')
        owner=User.objects.create_user(username='pilot-owner',email='pilot-owner@example.test')
        Membership.objects.create(user=owner,agency=agency,role='admin')
        managers=[]
        for n in range(2):
            user=User.objects.create_user(username=f'pilot-pm-{n}',email=f'pilot-pm-{n}@example.test')
            Membership.objects.create(user=user,agency=agency,role='pm');managers.append(user)
        tenant=User.objects.create_user(username='pilot-tenant',email='pilot-tenant@example.test')
        Membership.objects.create(user=tenant,agency=agency,role='tenant')
        properties=[Property.objects.create(agency=agency,manager=managers[n%2],name=f'Synthetic {n}',address=f'Synthetic address {n}') for n in range(100)]
        for prop in properties:
            for n in range(2):MaintenanceRequest.objects.create(property=prop,reported_by=tenant,title=f'Synthetic repair {n}',description='Synthetic test only',category='Plumbing')
        Tenancy.objects.create(user=tenant,property=properties[0],email=tenant.email)
        foreign=Agency.objects.create(name='Foreign agency')
        foreign_home=Property.objects.create(agency=foreign,name='FOREIGN PRIVATE',address='FOREIGN PRIVATE ADDRESS')
        MaintenanceRequest.objects.create(property=foreign_home,reported_by=tenant,title='FOREIGN PRIVATE JOB',description='Private',category='Plumbing')
        self.client.force_login(owner)
        self.assertEqual(len(self.client.get('/api/maintenance/context/').json()['properties']),100)
        identifiers=set()
        for page in range(1,5):
            response=self.client.get('/api/maintenance/requests/',{'page':page})
            self.assertEqual(response.status_code,200)
            data=response.json();self.assertEqual(data['count'],200)
            self.assertEqual(len(data['results']),50)
            self.assertNotIn('FOREIGN PRIVATE',response.content.decode())
            identifiers.update(job['id'] for job in data['results'])
        self.assertEqual(len(identifiers),200)
        self.client.force_login(managers[0])
        self.assertEqual(self.client.get('/api/maintenance/requests/').json()['count'],100)
        self.client.force_login(tenant)
        self.assertEqual(self.client.get('/api/maintenance/requests/').json()['count'],2)
