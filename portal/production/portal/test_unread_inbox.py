import uuid
from django.test import TestCase, override_settings
from django.urls import reverse
from . import test_notifications as fixtures
from .models import OperationsInboxItem, User
from .events import record


@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False,ALLOWED_HOSTS=['testserver'])
class UnreadInboxTests(TestCase):
    setUpTestData=classmethod(fixtures.EventWorkflowTests.setUpTestData.__func__)
    new_job=fixtures.EventWorkflowTests.new_job
    post=fixtures.EventWorkflowTests.post

    def setUp(self):
        fixtures.EventWorkflowTests.setUp(self)
        self.new_job(as_pm=True)
        event=record(self.job,self.pm,'workflow_event',str(uuid.uuid4()),{'action':'Sample inbox message','decision_id':str(uuid.uuid4())},private=True)
        self.item=OperationsInboxItem.objects.get(event=event)
        self.feed=reverse('operations_notifications')

    def test_unread_filter_hides_saved_reads_without_deleting_history(self):
        self.client.force_login(self.ops)
        initial=self.client.get(self.feed,{'unread':'1'}).json()
        self.assertIn(self.item.pk,[item['id'] for item in initial['items']])
        before=(self.job.version,self.job.status)
        self.assertEqual(self.post(reverse('operations_notification_state',args=[self.item.pk]),{'read':True}).status_code,200)
        result=self.client.get(self.feed,{'unread':'1'}).json()
        self.assertNotIn(self.item.pk,[item['id'] for item in result['items']])
        self.assertEqual(result['unread_count'],initial['unread_count']-1)
        self.assertIn(self.item.pk,[item['id'] for item in self.client.get(self.feed).json()['items']])
        self.job.refresh_from_db();self.assertEqual((self.job.version,self.job.status),before)
        other=User.objects.create_user(username='second-inbox@example.test',is_staff=True,is_superuser=True)
        self.client.force_login(other)
        self.assertIn(self.item.pk,[item['id'] for item in self.client.get(self.feed,{'unread':'1'}).json()['items']])

    def test_filter_rejects_invalid_values_and_keeps_role_boundary(self):
        self.client.force_login(self.ops);self.assertEqual(self.client.get(self.feed,{'unread':'invalid'}).status_code,400)
        self.client.force_login(self.pm);self.assertEqual(self.client.get(self.feed,{'unread':'1'}).status_code,403)
