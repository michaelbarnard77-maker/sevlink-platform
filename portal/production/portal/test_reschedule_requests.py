import json
import uuid
from datetime import timedelta
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from . import test_operational_workflow as fixtures
from . import test_scheduling as scheduling
from .models import AttendanceRequest, OperationsInboxItem, UserJobNotification, User


@override_settings(**scheduling.SETTINGS)
class RescheduleRequestTests(TestCase):
    setUpTestData=classmethod(fixtures.AttendanceAndFinanceTests.setUpTestData.__func__)
    setUp=fixtures.AttendanceAndFinanceTests.setUp
    prepare=fixtures.AttendanceAndFinanceTests.prepare
    confirm=fixtures.AttendanceAndFinanceTests.confirm

    def request_date(self,user,key=None):
        self.client.force_login(user);self.job.refresh_from_db()
        self.last_request=dict(version=self.job.version,preference='date',date=str(self.when+timedelta(days=2)),window='09:00–13:00')
        return self.client.post(reverse('workflow_action',args=[self.job.pk,'attendance-request']),json.dumps(self.last_request),content_type='application/json',HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))

    def test_pm_reschedule_keeps_booking_and_creates_one_action_until_confirmed(self):
        values=self.prepare()
        self.assertEqual(self.client.get(reverse('workflow_stages')).json()['reschedule_requests'],[])
        self.assertEqual(self.confirm(values).status_code,201)
        self.arrival.refresh_from_db();old=self.arrival.appointment
        key=uuid.uuid4();result=self.request_date(self.pm,key)
        self.assertEqual(result.status_code,200,result.content)
        old.refresh_from_db();self.assertIsNone(old.cancelled_at)
        items=OperationsInboxItem.objects.filter(event__request=self.job,event__details__action='Reschedule date requested')
        self.assertEqual(items.count(),1)
        self.assertTrue(UserJobNotification.objects.filter(event=items.get().event,user=self.ops).exists())
        # Repeating an identical browser submission does not duplicate the request or notification.
        replay=self.client.post(reverse('workflow_action',args=[self.job.pk,'attendance-request']),json.dumps(self.last_request),content_type='application/json',HTTP_IDEMPOTENCY_KEY=str(key))
        self.assertEqual(replay.status_code,200,replay.content)
        self.assertEqual(items.count(),1)
        self.client.force_login(self.ops)
        pending=self.client.get(reverse('workflow_stages')).json()['reschedule_requests']
        self.assertEqual(len(pending),1);self.assertEqual(pending[0]['job'],str(self.job.pk))
        self.assertEqual(pending[0]['date'],str(self.when+timedelta(days=2)))
        request=AttendanceRequest.objects.get(request=self.job,status='pending');self.job.refresh_from_db()
        values.update(version=self.job.version,attendance=request.pk,appointment=old.pk,date=str(self.when+timedelta(days=2)),starts_at=str(self.when+timedelta(days=2))+'T09:00:00+02:00',ends_at=str(self.when+timedelta(days=2))+'T10:00:00+02:00',reason='Client requested another date',client_confirmed=True,contact_category='pm')
        result=self.confirm(values);self.assertEqual(result.status_code,201,result.content)
        old.refresh_from_db();self.assertIsNotNone(old.cancelled_at)
        self.assertEqual(self.client.get(reverse('workflow_stages')).json()['reschedule_requests'],[])

    def test_only_designated_access_contact_can_request_and_initial_date_is_not_reschedule(self):
        values=self.prepare();self.assertEqual(self.confirm(values).status_code,201)
        self.assertEqual(self.request_date(self.tenant).status_code,403)
        self.job.access_responsibility='sevlink';self.job.save(update_fields=['access_responsibility'])
        self.assertEqual(self.request_date(self.pm).status_code,403)
        self.assertEqual(self.request_date(self.tenant).status_code,200)
        self.client.force_login(self.ops)
        self.assertEqual(len(self.client.get(reverse('workflow_stages')).json()['reschedule_requests']),1)
        self.client.force_login(self.pm)
        self.assertEqual(self.client.get(reverse('workflow_stages')).json()['reschedule_requests'],[])
