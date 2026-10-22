import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta, date
from unittest import skipUnless
from unittest.mock import patch
from django.contrib.auth.models import Permission
from django.db import connection, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from .models import (AppointmentOverride, JobAssignment, MaintenanceRequest, SubcontractorTeam,
    TeamAppointment, User, JobInvoice, InvoicePayment, TradeCategory, Membership)
from .test_regions import fixtures as region_fixtures, SETTINGS
from .test_attachments import document
from .test_suppliers import SupplierTests
from .suppliers import TZ


def fixtures(cls):
    region_fixtures(cls)
    trade,_=TradeCategory.objects.get_or_create(name='Plumbing');cls.partner.trades.add(trade)
    cls.crew=SubcontractorTeam.objects.create(subcontractor=cls.partner,name='Team A',working_days=list(range(7)))
    cls.crew_b=SubcontractorTeam.objects.create(subcontractor=cls.partner,name='Team B',working_days=list(range(7)))
    cls.scheduler=User.objects.create_user(username='scheduler',email='scheduler@example.test',is_staff=True,first_name='PRIVATE scheduler identity')
    cls.scheduler.user_permissions.add(Permission.objects.get(codename='operate_schedule'))
    cls.finance=User.objects.create_user(username='finance',email='finance@example.test',is_staff=True)
    cls.finance.user_permissions.add(Permission.objects.get(codename='manage_supplier_payments'))
    cls.more_jobs=[MaintenanceRequest.objects.create(property=cls.home,reported_by=cls.tenant,title=f'Schedule job {i}',description='Synthetic scheduling test',category='Plumbing') for i in range(3)]
    from .models import SchedulingArrangement
    for job in cls.more_jobs:SchedulingArrangement.objects.create(request=job,actor=cls.ops,reason='Synthetic agreed scheduling terms')
    cls.monday=timezone.localdate()-timedelta(days=timezone.localdate().weekday())


def data(job,supplier,crew,start='09:00',end='12:00',day=None,**extra):
    job.refresh_from_db()
    day=day or timezone.localdate()-timedelta(days=timezone.localdate().weekday())
    return dict(job=str(job.pk),version=job.version,subcontractor=str(supplier.pk),team=str(crew.pk),
        starts_at=f'{day}T{start}:00+02:00',ends_at=f'{day}T{end}:00+02:00',submission_key=str(uuid.uuid4()),**extra)


def save(client,body):
    return client.post(reverse('operations_calendar_save'),json.dumps(body),content_type='application/json')


@override_settings(**SETTINGS)
class SchedulingTests(TestCase):
    @classmethod
    def setUpTestData(cls): fixtures(cls)
    setUp=SupplierTests.setUp

    def login_scheduler(self): self.client.force_login(self.scheduler)
    def book(self,job=None,crew=None,**kw):
        return save(self.client,data(job or self.job,self.partner,crew or self.crew,**kw))

    def test_week_navigation_proportional_positions_multiple_jobs_and_location(self):
        self.login_scheduler()
        self.assertEqual(self.book().status_code,201)
        self.assertEqual(self.book(self.cape_job,start='12:00',end='14:00').status_code,201)
        response=self.client.get(reverse('operations_calendar'),{'week':str(self.monday+timedelta(days=4))})
        self.assertEqual(response.status_code,200,response.content)
        d=response.json();self.assertEqual(d['week_start'],str(self.monday));self.assertEqual(len(d['days']),7)
        self.assertEqual(d['next'],str(self.monday+timedelta(days=7)))
        a,b=d['appointments'];self.assertEqual((a['left_percent'],a['width_percent']),(0,37.5))
        self.assertEqual((b['left_percent'],b['width_percent']),(37.5,25))
        self.assertEqual(self.client.get(reverse('operations_calendar'),{'week':d['next']}).json()['appointments'],[])
        d=self.client.get(reverse('operations_calendar'),{'city':self.cape.pk,'trade':'Plumbing','team':str(self.crew.pk)}).json()
        self.assertEqual([a['job'] for a in d['appointments']],[str(self.cape_job.pk)])
        search=self.client.get(reverse('operations_calendar'),{'job_search':'SV-'+str(self.job.pk).upper()}).json()
        self.assertEqual([j['id'] for j in search['jobs']],[str(self.job.pk)])

    def test_overlap_rejects_and_rolls_back_new_assignment(self):
        self.login_scheduler();self.book()
        response=self.book(self.cape_job,start='10:00',end='11:00')
        self.assertEqual(response.status_code,409,response.content)
        self.assertEqual(JobAssignment.objects.count(),1)
        self.assertEqual(TeamAppointment.objects.count(),1)
        self.cape_job.refresh_from_db();self.assertEqual(self.cape_job.version,1)
        self.assertEqual(self.book(self.cape_job,self.crew_b,start='10:00',end='11:00').status_code,201)

    def test_only_superadmin_can_override_with_a_reason_and_audit(self):
        self.login_scheduler();self.book()
        forged=data(self.cape_job,self.partner,self.crew,start='10:00',end='11:00',override_reason='Forged permission')
        self.assertEqual(save(self.client,forged).status_code,403)
        self.client.force_login(self.ops)
        self.assertEqual(self.book(self.cape_job,start='10:00',end='11:00').status_code,409)
        self.assertEqual(self.book(self.cape_job,start='10:00',end='11:00',override_reason='   ').status_code,409)
        response=self.book(self.cape_job,start='10:00',end='11:00',override_reason='Approved shared site visit')
        self.assertEqual(response.status_code,201,response.content)
        override=AppointmentOverride.objects.get()
        self.assertEqual(override.actor,self.ops);self.assertEqual(len(override.overlapping_ids),1)
        self.assertIsNotNone(override.created_at)
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError): override.delete()

    def test_override_does_not_bypass_working_days_unavailable_or_coverage(self):
        from .models import TeamUnavailableDate
        TeamUnavailableDate.objects.create(team=self.crew,date=self.monday,reason='Unavailable',actor=self.ops)
        self.assertEqual(self.book(override_reason='Not valid for unavailable dates').status_code,400)
        self.assertEqual(self.book(start='08:00',end='10:00',override_reason='Not valid for hours').status_code,400)
        self.assertEqual(TeamAppointment.objects.count(),0)

    def test_idempotency_stale_version_reschedule_cancel_and_history(self):
        self.login_scheduler()
        body=data(self.job,self.partner,self.crew)
        first=save(self.client,body);self.assertEqual(first.status_code,201)
        self.assertEqual(save(self.client,body).status_code,200)
        self.assertEqual(save(self.client,{**body,'ends_at':f'{self.monday}T13:00:00+02:00'}).status_code,409)
        stale=data(self.cape_job,self.partner,self.crew,start='12:00',end='13:00');stale['version']=0
        self.assertEqual(save(self.client,stale).status_code,409)
        replacement=data(self.job,self.partner,self.crew_b,start='14:00',end='15:00',appointment=first.json()['id'],reason='Tenant requested later time')
        moved=save(self.client,replacement);self.assertEqual(moved.status_code,201,moved.content)
        self.assertEqual(save(self.client,replacement).status_code,200)
        original=TeamAppointment.objects.get(pk=first.json()['id']);self.assertIsNotNone(original.cancelled_at)
        latest=TeamAppointment.objects.get(pk=moved.json()['id']);self.assertEqual(latest.rescheduled_from_id,original.pk)
        self.assertEqual(latest.team,self.crew_b);self.assertEqual(JobAssignment.objects.count(),2)
        self.assertEqual(save(self.client,{'cancel':latest.pk,'reason':'Visit no longer required'}).status_code,200)
        self.client.force_login(self.ops)
        self.assertEqual(save(self.client,{'cancel':latest.pk,'reason':'Repeat cancellation'}).status_code,200)
        history=self.client.get(reverse('operations_calendar_job',args=[self.job.pk])).json()['appointments']
        self.assertEqual(len(history),2);self.assertTrue(all(a['cancelled'] for a in history))

    def test_failed_reschedule_preserves_original_booking_and_assignment(self):
        self.login_scheduler();first=self.book().json()
        response=self.book(start='17:00',end='18:00',appointment=first['id'],reason='Invalid hours')
        self.assertEqual(response.status_code,400)
        self.assertIsNone(TeamAppointment.objects.get().cancelled_at)
        self.assertEqual(JobAssignment.objects.count(),1)

    def test_public_progress_updates_preserve_privacy_and_actor_masking(self):
        self.login_scheduler();self.book()
        for state in ('reviewed','scheduled','on_site','attended','completed'):
            self.job.refresh_from_db()
            response=self.client.post(reverse('operations_calendar_progress',args=[self.job.pk]),json.dumps({'status':state,'version':self.job.version}),content_type='application/json')
            self.assertEqual(response.status_code,200,response.content)
            tenant=Client();tenant.force_login(self.tenant)
            public=tenant.get(reverse('maintenance_detail',args=[self.job.pk]))
            self.assertEqual(public.json()['status'],state)
            text=public.content.decode()
            for private in ('PRIVATE scheduler identity',str(self.crew.pk),self.partner.name,'appointment_changed','job_assigned'):
                self.assertNotIn(private,text)
        self.assertEqual(self.job.status_events.count(),5)
        self.assertEqual(self.client.get(reverse('maintenance_collection')).json()['count'],0)

    def test_plain_staff_agency_tenant_private_client_and_finance_cannot_schedule(self):
        plain=User.objects.create_user(username='plain-cal',email='plain-cal@example.test',is_staff=True)
        private=User.objects.create_user(username='private-cal',email='private-cal@example.test')
        for user in (plain,private,self.pm,self.tenant,self.finance):
            c=Client();c.force_login(user)
            self.assertEqual(c.get(reverse('operations_calendar')).status_code,403)
            self.assertEqual(save(c,data(self.job,self.partner,self.crew)).status_code,403)
        self.pm.is_staff=True;self.pm.save();self.pm.user_permissions.add(Permission.objects.get(codename='operate_schedule'))
        self.client.force_login(self.pm)
        self.assertEqual(self.client.get(reverse('operations_calendar')).status_code,403)
        self.client.logout();self.assertEqual(self.client.get(reverse('operations_calendar')).status_code,401)
        c=Client(enforce_csrf_checks=True);c.force_login(self.scheduler)
        self.assertEqual(save(c,data(self.job,self.partner,self.crew)).status_code,403)

    def invoice(self,number,amount,due):
        response=self.client.post(reverse('maintenance_invoice',args=[self.job.pk]),{'number':number,'amount':amount,'due_date':str(due),'subcontractor':str(self.partner.pk),'attachments':document()},HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(response.status_code,201,response.content)
        # Historical due-date fixtures, independent of the new upload-next-Monday rule.
        JobInvoice.objects.filter(pk=response.json()['id']).update(due_date=due)
        return JobInvoice.objects.get(pk=response.json()['id'])

    def test_monday_totals_partial_payments_finance_permissions_and_private_pdf(self):
        self.book()
        today=timezone.localdate();monday=today+timedelta(days=(0-today.weekday())%7)
        first=self.invoice('DUE-1','300.00',today-timedelta(days=1))
        self.invoice('DUE-2','500.00',monday);self.invoice('LATER','700.00',monday+timedelta(days=1))
        self.client.force_login(self.ops)
        pay={'version':first.version,'amount':'100.00','paid_on':str(today),'reference':'EXTERNAL-STEP9'}
        response=self.client.post(reverse('maintenance_invoice_payment',args=[self.job.pk,first.pk]),json.dumps(pay),content_type='application/json',HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(response.status_code,201,response.content)
        d=self.client.get(reverse('operations_monday_payments')).json()
        self.assertEqual((d['outstanding_total'],d['overdue_total'],d['count']),('700.00','200.00',2))
        self.assertEqual(self.client.get(reverse('operations_monday_payments'),{'period':'all'}).json()['outstanding_total'],'1400.00')
        self.assertEqual(self.client.get(reverse('operations_monday_payments'),{'period':'overdue'}).json()['count'],1)
        response=self.client.get(reverse('maintenance_invoice_pdf',args=[self.job.pk,first.pk]))
        self.assertEqual(response.status_code,200);self.assertTrue(b''.join(response.streaming_content).startswith(b'%PDF-'))
        self.assertEqual(self.client.get(reverse('supplier_profile',args=[self.partner.pk])).status_code,200)
        self.assertEqual(InvoicePayment.objects.count(),1)  # Viewing Monday never records a payment.
        for user in (self.scheduler,self.pm,self.tenant):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse('operations_monday_payments')).status_code,403)
        self.client.force_login(self.ops)
        JobInvoice.objects.filter(pk=first.pk).update(reconciliation_required=True)
        d=self.client.get(reverse('operations_monday_payments')).json();self.assertTrue(d['results'][0]['attention'])

    def test_monday_on_monday_is_today_and_cancelled_job_status(self):
        with patch('portal.scheduling.timezone.localdate',return_value=date(2030,1,7)):
            self.assertEqual(self.client.get(reverse('operations_monday_payments')).json()['monday'],'2030-01-07')
        self.login_scheduler()
        response=self.client.post(reverse('operations_calendar_progress',args=[self.job.pk]),json.dumps({'status':'cancelled','version':1}),content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.book().status_code,409)


@override_settings(**SETTINGS)
@skipUnless(connection.vendor=='postgresql','PostgreSQL concurrency and row locking')
class SchedulingConcurrencyTests(TransactionTestCase):
    def setUp(self): fixtures(self)
    def race(self,bodies):
        def action(body):
            try:
                c=Client();c.force_login(User.objects.get(pk=self.scheduler.pk));return save(c,body).status_code
            finally:
                connections.close_all()
                for alias in connections:self.assertIsNone(connections[alias].connection)
        with ThreadPoolExecutor(max_workers=2) as executor:return list(executor.map(action,bodies))

    def test_concurrent_same_team_bookings_create_only_one_and_no_orphan_assignments(self):
        statuses=self.race([data(self.job,self.partner,self.crew),data(self.cape_job,self.partner,self.crew)])
        self.assertEqual(sorted(statuses),[201,409]);self.assertEqual(TeamAppointment.objects.count(),1);self.assertEqual(JobAssignment.objects.count(),1)

    def test_concurrent_different_teams_succeed(self):
        statuses=self.race([data(self.job,self.partner,self.crew),data(self.cape_job,self.partner,self.crew_b)])
        self.assertEqual(statuses,[201,201]);self.assertEqual(TeamAppointment.objects.count(),2)

    def test_concurrent_reschedules_preserve_one_replacement(self):
        c=Client();c.force_login(self.scheduler);first=save(c,data(self.job,self.partner,self.crew)).json()
        bodies=[data(self.job,self.partner,self.crew,start=start,end=end,appointment=first['id'],reason='Concurrent reschedule') for start,end in [('13:00','14:00'),('15:00','16:00')]]
        self.assertEqual(sorted(self.race(bodies)),[201,409]);self.assertEqual(TeamAppointment.objects.count(),2)
