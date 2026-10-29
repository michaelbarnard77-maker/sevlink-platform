"""Submission routing is based on the authenticated role, never client flags."""
import uuid
from django.test import TestCase,override_settings
from django.urls import reverse
from . import test_notifications as fixtures
from .models import MaintenanceRequest,OperationsNotification,UserJobNotification

@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False)
class SubmissionRoutingTests(TestCase):
    setUpTestData=classmethod(fixtures.EventWorkflowTests.setUpTestData.__func__)
    setUp=fixtures.EventWorkflowTests.setUp
    post=fixtures.EventWorkflowTests.post

    def submit(self,user,key=None,**fields):
        self.client.force_login(user)
        return self.post(reverse('maintenance_collection'),dict(property=str(self.home.pk),title='Routing repair',description='Synthetic test',category='Plumbing',**fields),key)

    def test_tenant_goes_to_pm_only_and_cannot_authorise_work(self):
        result=self.submit(self.tenant)
        self.assertEqual(result.status_code,201,result.content)
        job=MaintenanceRequest.objects.get(pk=result.json()['id'])
        self.assertEqual((job.status,job.job_type),('awaiting_review','unclassified'))
        self.assertEqual(OperationsNotification.objects.count(),0)
        self.assertTrue(UserJobNotification.objects.filter(user=self.pm,event__request=job).exists())
        self.assertFalse(UserJobNotification.objects.filter(user=self.ops,event__request=job).exists())
        self.assertEqual(self.submit(self.tenant,job_type='callout',limit='1000').status_code,400)
        self.assertEqual(MaintenanceRequest.objects.count(),1)

    def test_pm_and_admin_go_directly_to_sevlink_with_retry_dedup(self):
        for user in (self.pm,self.admin):
            key=uuid.uuid4()
            response=self.submit(user,key)
            self.assertEqual(response.status_code,201,response.content)
            job=MaintenanceRequest.objects.get(pk=response.json()['id'])
            self.assertEqual((job.status,job.job_type),('reviewed','quoted'))
            self.assertFalse(job.authorised_at)
            self.assertTrue(UserJobNotification.objects.filter(user=self.ops,event__request=job).exists())
            self.assertEqual(self.submit(user,key).status_code,200)
            self.assertEqual(OperationsNotification.objects.filter(event__request=job).count(),1)
            self.assertEqual(job.status_events.count(),1)

    def test_callout_needs_limit_and_portfolio_isolation_is_preserved(self):
        self.assertEqual(self.submit(self.pm,job_type='callout').status_code,400)
        self.assertEqual(MaintenanceRequest.objects.count(),0)
        result=self.submit(self.pm,job_type='callout',limit='1500',access_responsibility='sevlink')
        self.assertEqual(result.status_code,201,result.content)
        job=MaintenanceRequest.objects.get(pk=result.json()['id'])
        self.assertEqual(job.spending_limit,1500)
        self.assertEqual(job.authorised_by,self.pm)
        self.assertTrue(job.job_number)
        for user in (self.other_pm,self.foreign):
            self.assertEqual(self.submit(user).status_code,400)
