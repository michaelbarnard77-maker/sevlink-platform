import json
from datetime import timedelta
from decimal import Decimal
from django.test import TestCase,override_settings
from django.urls import reverse
from django.utils import timezone
from .test_manual_documents import ManualDocumentTests
from .test_notifications import EventWorkflowTests
from .models import (MaintenanceRequest,Property,JobQuotation,JobActionRequest,PortalAcknowledgement,
    SchedulingArrangement,TeamAppointment,JobAssignment,WebsiteIssue,JobInvoice,User,DocumentSequence)

@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False)
class CustomerPortalTests(TestCase):
    setUpTestData=classmethod(EventWorkflowTests.setUpTestData.__func__)
    setUp=ManualDocumentTests.setUp
    new_job=EventWorkflowTests.new_job
    post=EventWorkflowTests.post
    quote=ManualDocumentTests.quote
    invoice=ManualDocumentTests.invoice
    payment=ManualDocumentTests.payment
    sent=ManualDocumentTests.sent

    def page(self,section,user=None,**query):
        self.client.force_login(user or self.pm)
        return self.client.get(reverse('customer_portal_section',args=[section]),query)

    def test_attention_scoped_and_removed_after_review(self):
        other=Property.objects.create(agency=self.agency,manager=self.other_pm,name='Other PM',address='OTHER PM PRIVATE')
        MaintenanceRequest.objects.create(property=other,reported_by=self.tenant,title='OTHER PRIVATE REPAIR',description='Private',category='Plumbing')
        data=self.page('attention').json()['items'];self.assertEqual(len(data),1)
        self.assertEqual(data[0]['reference'],self.job.reference)
        self.assertEqual(data[0]['job'],str(self.job.pk))
        self.assertEqual(self.page('attention',self.other_pm).json()['items'][0]['property'],'OTHER PM PRIVATE')
        self.assertEqual(self.page('attention',self.foreign).json()['items'],[])
        self.client.force_login(self.pm)
        response=self.client.patch(self.detail_url,json.dumps({'status':'reviewed','version':self.job.version}),content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.page('attention').json()['items'],[])

    def test_quote_decision_disappears_and_revision_is_not_duplicate_pm_action(self):
        self.client.force_login(self.ops);q=self.sent()
        items=self.page('attention').json()['items']
        self.assertEqual(sum(i['target']=='quotation' for i in items),1)
        self.client.force_login(self.pm)
        self.assertEqual(self.post(reverse('maintenance_quote_decision',args=[self.job.pk,q['id']]),{'version':q['version'],'status':'revision_requested','reason':'Please revise'}).status_code,200)
        self.assertFalse(any(i['target']=='quotation' for i in self.page('attention').json()['items']))
        self.assertEqual(self.page('quotations',self.tenant).status_code,403)

    def test_finance_half_deposit_totals_and_staff_confirmation(self):
        self.client.force_login(self.ops);invoice=self.invoice().json()
        before=self.page('accounts').json();self.assertEqual(before['outstanding'],'1000.00')
        from .customer_portal import deposit_state
        self.assertFalse(deposit_state(self.job)['ready'])
        self.client.force_login(self.pm)
        self.assertEqual(self.payment(invoice,amount='500').status_code,403)
        self.client.force_login(self.ops)
        invoice=self.payment(invoice,amount='500').json()
        data=self.page('accounts',filter='deposit').json()
        self.assertEqual(len(data['invoices']),1);self.assertEqual(data['outstanding'],'500.00')
        self.assertEqual(data['invoices'][0]['invoice']['net_paid_amount'],'500.00')
        self.assertTrue(deposit_state(self.job)['ready'])
        self.assertEqual(self.page('accounts',filter='paid').json()['invoices'],[])
        self.client.force_login(self.ops);self.assertEqual(self.payment(invoice,amount='500').status_code,201)
        self.assertEqual(self.page('accounts',filter='paid').json()['outstanding'],'0.00')
        self.assertFalse(any(i['target']=='invoice' for i in self.page('attention').json()['items']))

    def test_overdue_priority_completed_balance_and_supplier_privacy(self):
        self.client.force_login(self.ops)
        self.invoice(number='Public',due_date=str(timezone.localdate()-timedelta(days=1)))
        self.invoice(number='PRIVATE-SUPPLIER-REF',visibility='internal')
        result=self.page('accounts',filter='overdue')
        self.assertEqual(result.json()['overdue'],'1000.00')
        self.assertNotIn('PRIVATE-SUPPLIER',result.content.decode())
        self.assertEqual(self.page('accounts',self.tenant).status_code,403)
        self.assertEqual(self.page('accounts',self.other_pm).json()['invoices'],[])
        self.assertEqual(self.page('accounts',self.foreign).json()['invoices'],[])
        self.job.status='completed';self.job.save(update_fields=['status'])
        items=self.page('attention').json()['items']
        self.assertEqual(len(items),1);self.assertIn('final payment',items[0]['action'])

    def test_urgency_and_explicit_actions_resolve_with_role_boundaries(self):
        self.job.urgency='safety';self.job.save(update_fields=['urgency'])
        action=JobActionRequest.objects.create(request=self.job,created_by=self.ops,text='Please provide access availability',audience='pm')
        items=self.page('attention').json()['items'];self.assertTrue(all(i['priority']==0 for i in items))
        url=reverse('customer_portal_action',args=[self.job.pk])
        self.client.force_login(self.tenant)
        self.assertEqual(self.post(url,{'resolve':action.pk}).status_code,403)
        self.client.force_login(self.pm);self.assertEqual(self.post(url,{'resolve':action.pk}).status_code,200)
        self.assertFalse(any(i['target']=='action' for i in self.page('attention').json()['items']))
        self.assertEqual(self.post(url,{'arrangement':'Forged terms'}).status_code,403)

    def test_deposit_invoice_uses_approved_job_amount_not_half_of_smaller_invoice(self):
        from .customer_portal import deposit_state
        self.client.force_login(self.ops);q=self.sent()
        self.client.force_login(self.pm)
        self.assertEqual(self.post(reverse('maintenance_quote_decision',args=[self.job.pk,q['id']]),{'version':q['version'],'status':'approved','reason':'Approved scope'}).status_code,200)
        self.client.force_login(self.ops);invoice=self.invoice(amount='500').json();invoice=self.payment(invoice,amount='250').json()
        self.assertFalse(deposit_state(self.job)['ready'])
        self.assertEqual(self.page('accounts',filter='deposit').json()['invoices'],[])
        self.client.force_login(self.ops);self.payment(invoice,amount='250')
        self.assertTrue(deposit_state(self.job)['ready'])
        self.assertEqual(len(self.page('accounts',filter='deposit').json()['invoices']),1)

    def test_refunds_remove_deposit_readiness_and_duplicate_requests_coalesce(self):
        from .customer_portal import deposit_state
        self.client.force_login(self.ops);invoice=self.invoice().json();invoice=self.payment(invoice,amount='500').json()
        self.assertTrue(deposit_state(self.job)['ready'])
        from .models import InvoicePayment
        payment=InvoicePayment.objects.get(invoice_id=invoice['id'])
        response=self.post(reverse('maintenance_invoice_adjustment',args=[self.job.pk,invoice['id'],'refunds']),{
            'version':invoice['version'],'payment_id':payment.pk,'amount':'1','refunded_on':str(timezone.localdate()),
            'reason':'Synthetic verified refund','reference':'Synthetic refund','confirmation':'REFUND'})
        self.assertEqual(response.status_code,201,response.content)
        self.assertFalse(deposit_state(self.job)['ready'])
        action_url=reverse('customer_portal_action',args=[self.job.pk])
        body={'text':'Please provide safe access availability','audience':'pm'}
        self.assertEqual(self.post(action_url,body).status_code,200)
        self.assertEqual(self.post(action_url,body).status_code,200)
        self.assertEqual(JobActionRequest.objects.filter(request=self.job).count(),1)

    def test_malformed_portal_mutations_fail_without_writes(self):
        self.client.force_login(self.ops)
        url=reverse('customer_portal_action',args=[self.job.pk])
        for body in ('{bad json',json.dumps({'unknown':'value'}),json.dumps({'text':'Test','audience':'pm','due_date':{}})):
            self.assertEqual(self.client.post(url,body,content_type='application/json').status_code,400)
        self.assertEqual(JobActionRequest.objects.count(),0)
        self.client.force_login(self.pm)
        self.assertEqual(self.client.post(reverse('customer_portal_issue'),json.dumps({'subject':[],'description':'Test'}),content_type='application/json').status_code,400)

    def test_updates_and_issue_reports_are_private_and_saved(self):
        self.assertTrue(self.page('updates').json()['updates'])
        self.page('issues',self.tenant)
        self.assertEqual(self.post(reverse('customer_portal_issue'),{'subject':'Navigation problem','description':'Synthetic report'}).status_code,201)
        self.assertEqual(WebsiteIssue.objects.count(),1)
        self.assertEqual(len(self.page('issues',self.tenant).json()['issues']),1)
        self.assertEqual(self.page('issues',self.cotenant).json()['issues'],[])
        self.assertEqual(self.client.get(reverse('operations_website_issues')).status_code,403)
        self.client.force_login(self.ops);self.assertEqual(len(self.client.get(reverse('operations_website_issues')).json()['issues']),1)

    def test_job_numbers_immutable_and_legacy_reference_retained(self):
        self.assertRegex(self.job.reference,r'^REQ-\d{4,}$')
        self.assertIsNone(self.job.job_number)
        self.client.force_login(self.pm);data=self.client.get(self.detail_url).json()
        self.assertEqual(data['legacy_reference'],'SV-'+str(self.job.pk).upper())
        self.job.job_number=1
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):self.job.save()


from .test_scheduling import fixtures as schedule_fixtures,data,save
@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False)
class CustomerCalendarTests(TestCase):
    @classmethod
    def setUpTestData(cls):schedule_fixtures(cls)

    def test_calendar_only_published_times_and_no_supplier_fields(self):
        self.client.force_login(self.ops)
        self.assertEqual(save(self.client,data(self.job,self.partner,self.crew)).status_code,201)
        url=reverse('customer_portal_section',args=['calendar'])
        self.client.force_login(self.pm);self.assertEqual(self.client.get(url).json()['appointments'],[])
        a=TeamAppointment.objects.get()
        self.client.force_login(self.ops)
        self.assertEqual(self.client.post(reverse('customer_portal_action',args=[self.job.pk]),json.dumps({'appointment':a.pk,'customer_visible':True}),content_type='application/json').status_code,200)
        for user in (self.pm,self.tenant):
            self.client.force_login(user);response=self.client.get(url)
            self.assertEqual(len(response.json()['appointments']),1)
            for secret in ('subcontractor','supplier','team','override','cancellation_reason','PRIVATE'):
                self.assertNotIn(secret,response.content.decode())
        stranger=User.objects.create_user(username='stranger',email='stranger@example.test')
        from .models import Membership
        Membership.objects.create(user=stranger,agency=self.agency,role='tenant')
        self.client.force_login(stranger);self.assertEqual(self.client.get(url).json()['appointments'],[])
        self.assertEqual(self.client.get(url,{'week':'bad-date'}).status_code,400)

    def test_cancelled_alert_acknowledged_without_job_change(self):
        self.client.force_login(self.ops)
        self.assertEqual(save(self.client,data(self.job,self.partner,self.crew,customer_visible=True)).status_code,201)
        a=TeamAppointment.objects.get();a.cancelled_at=timezone.now();a.cancellation_reason='PRIVATE supplier scheduling note';a.save()
        self.client.force_login(self.pm)
        result=self.client.get(reverse('customer_portal_section',args=['attention'])).json()['items']
        item=next(r for r in result if r['target']=='appointment')
        self.assertEqual(self.client.post(reverse('customer_portal_acknowledge'),json.dumps({'key':item['key']}),content_type='application/json').status_code,200)
        after=self.client.get(reverse('customer_portal_section',args=['attention'])).json()['items']
        self.assertFalse(any(r['target']=='appointment' for r in after))
        self.job.refresh_from_db();self.assertNotEqual(self.job.status,'cancelled')

    def test_fifty_percent_deposit_or_explicit_arrangement_required(self):
        job=MaintenanceRequest.objects.create(property=self.home,reported_by=self.tenant,title='New deposit job',description='Synthetic',category='Plumbing')
        self.client.force_login(self.ops)
        body=data(job,self.partner,self.crew)
        self.assertEqual(save(self.client,body).status_code,409)
        self.assertFalse(JobAssignment.objects.filter(request=job).exists())
        SchedulingArrangement.objects.create(request=job,actor=self.ops,reason='Reviewed customer payment-on-completion arrangement')
        self.assertEqual(save(self.client,body).status_code,201)

from unittest import skipUnless
from concurrent.futures import ThreadPoolExecutor
from django.db import connection,connections
from django.test import TransactionTestCase

@skipUnless(connection.vendor=='postgresql','PostgreSQL job numbering concurrency')
class JobNumberConcurrencyTests(TransactionTestCase):
    def test_simultaneous_requests_get_distinct_persistent_numbers(self):
        from .models import Agency
        agency=Agency.objects.create(name='Synthetic sequence agency')
        user=User.objects.create_user(username='sequence',email='sequence@example.test')
        home=Property.objects.create(agency=agency,name='Synthetic',address='Synthetic')
        def create(_):
            try:return MaintenanceRequest.objects.create(property_id=home.pk,reported_by_id=user.pk,title='Concurrent test',description='Synthetic',category='Plumbing').request_number
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:values=list(pool.map(create,[1,2]))
        self.assertEqual(len(set(values)),2)
        self.assertEqual(abs(values[0]-values[1]),1)
