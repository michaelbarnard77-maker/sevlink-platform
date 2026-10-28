import uuid
from datetime import timedelta
from decimal import Decimal
from django.test import TestCase,override_settings
from django.urls import reverse
from django.utils import timezone
from . import test_notifications as fixtures
from . import test_manual_documents as documents
from .test_attachments import photo
from .models import MaintenanceRequest,WorkflowDecision,UserJobNotification,AdditionalAuthorisation,DepositVerification,CompletionRecord

@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False)
class OperationalWorkflowTests(TestCase):
    setUpTestData=classmethod(fixtures.EventWorkflowTests.setUpTestData.__func__)
    post=fixtures.EventWorkflowTests.post
    quote=documents.ManualDocumentTests.quote
    invoice=documents.ManualDocumentTests.invoice
    payment=documents.ManualDocumentTests.payment
    def setUp(self):
        fixtures.EventWorkflowTests.setUp(self)
        self.client.force_login(self.tenant)
        response=self.post(reverse('maintenance_collection'),dict(property=str(self.home.pk),title='Synthetic repair',description='Synthetic fault',category='Plumbing',urgency='safety'))
        self.assertEqual(response.status_code,201,response.content)
        self.job=MaintenanceRequest.objects.get(pk=response.json()['id'])
        self.quote_url=reverse('maintenance_quote',args=[self.job.pk]);self.invoice_url=reverse('maintenance_invoice',args=[self.job.pk]);self.detail_url=reverse('maintenance_detail',args=[self.job.pk])
    def act(self,operation,user=None,key=None,**v):
        self.client.force_login(user or self.pm);self.job.refresh_from_db()
        return self.post(reverse('workflow_action',args=[self.job.pk,operation]),dict(version=self.job.version,**v),key)
    def review(self,kind='callout'):
        r=self.act('review',job_type=kind,urgency='high',access_responsibility='pm',access_information='Synthetic access',limit='1000')
        self.assertEqual(r.status_code,200,r.content);self.job.refresh_from_db();return r
    def doc(self,kind):
        self.client.force_login(self.ops)
        r=self.client.post(reverse('workflow_documents',args=[self.job.pk]),{'kind':kind,'attachments':photo()})
        self.assertEqual(r.status_code,201,r.content)
    def test_safety_and_tenant_review_boundary(self):
        self.assertEqual(self.job.urgency,'normal');self.assertTrue(self.job.safety_concern);self.assertIsNone(self.job.job_number)
        self.assertTrue(UserJobNotification.objects.filter(user=self.pm,event__request=self.job).exists())
        self.assertFalse(UserJobNotification.objects.filter(user=self.foreign,event__request=self.job).exists())
        self.assertEqual(self.act('review',user=self.tenant,job_type='callout',urgency='urgent',access_responsibility='pm',limit='100').status_code,403)
    def test_pm_can_report_only_for_authorised_property(self):
        self.client.force_login(self.pm)
        values=dict(property=str(self.home.pk),title='PM report',description='Backend report',category='Electrical')
        self.assertEqual(self.post(reverse('maintenance_collection'),values).status_code,201)
        self.client.force_login(self.foreign);self.assertEqual(self.post(reverse('maintenance_collection'),values).status_code,400)
    def test_callout_number_ceiling_and_separate_quoted_additional_work(self):
        self.review();number=self.job.job_number
        self.assertIsNotNone(number);self.assertEqual(self.job.spending_limit,Decimal('1000'))
        from .workflow import eligible,check_ceiling
        self.assertTrue(eligible(self.job))
        with self.assertRaises(ValueError):check_ceiling(self.job,Decimal('1000.01'))
        r=self.act('additional-request',user=self.ops,limit='2000',reason='Extra work');self.assertEqual(r.status_code,200,r.content)
        extra=AdditionalAuthorisation.objects.get()
        r=self.act('additional-decision',additional=extra.pk,decision='quotation');self.assertEqual(r.status_code,200,r.content)
        extra.refresh_from_db();self.assertEqual(extra.linked_request.parent_request,self.job);self.assertIsNone(extra.linked_request.job_number)
        self.assertEqual(extra.linked_request.job_type,'quoted');self.assertNotEqual(extra.linked_request.request_number,self.job.request_number)
        self.job.refresh_from_db();self.assertEqual(self.job.job_number,number);self.assertEqual(self.job.spending_limit,1000)
        self.assertEqual(self.act('additional-decision',additional=extra.pk,decision='approved').status_code,409)
    def test_quotes_manual_and_scheduling_requires_explicit_superadmin_deposit_verification(self):
        self._exercise_deposit_verification()

    def test_new_deposit_on_historical_job_requires_explicit_verification(self):
        self._exercise_deposit_verification(historical=True)

    def _exercise_deposit_verification(self,historical=False):
        self.client.force_login(self.ops);self.assertEqual(self.quote().status_code,400)
        self.review('quoted');self.client.force_login(self.ops);q=self.quote(reference='SQ-MANUAL').json()
        sent=self.post(reverse('maintenance_quote_action',args=[self.job.pk,q['id'],'send']),{'version':q['version']}).json()
        self.client.force_login(self.pm)
        attention=self.client.get(reverse('workflow_stages'),{'stage':'attention'}).json()['results'][0]
        self.assertIn('Approve, reject or request quotation revision',[a['action'] for a in attention['attention_actions']])
        self.client.force_login(self.foreign);self.assertEqual(self.post(reverse('maintenance_quote_decision',args=[self.job.pk,q['id']]),dict(version=sent['version'],status='approved',reason='Forbidden')).status_code,404)
        self.client.force_login(self.admin);r=self.post(reverse('maintenance_quote_decision',args=[self.job.pk,q['id']]),dict(version=sent['version'],status='approved',reason='Approved'));self.assertEqual(r.status_code,200,r.content)
        self.job.refresh_from_db();self.assertIsNotNone(self.job.job_number)
        self.client.force_login(self.pm)
        attention=self.client.get(reverse('workflow_stages'),{'stage':'attention'}).json()['results'][0]
        self.assertEqual([a['action'] for a in attention['attention_actions']],['Awaiting invoice / deposit arrangements before scheduling'])
        self.assertEqual(self.act('attendance-request',preference='call').status_code,409)
        if historical:
            self.job.workflow_version=0;self.job.job_type='unclassified'
            self.job.save(update_fields=['workflow_version','job_type'])
        self.client.force_login(self.ops)
        uploaded=self.invoice(purpose='deposit');self.assertEqual(uploaded.status_code,201,uploaded.content)
        invoice=uploaded.json();self.assertEqual(invoice['purpose'],'deposit')
        self.client.force_login(self.pm)
        attention=self.client.get(reverse('workflow_stages'),{'stage':'attention'}).json()['results'][0]
        self.assertIn('Deposit required before scheduling',[a['action'] for a in attention['attention_actions']])
        self.assertEqual(self.payment(invoice,amount='500').status_code,403)
        self.assertEqual(self.act('verify-deposit',user=self.ops,confirmation='VERIFY').status_code,400)
        self.client.force_login(self.ops);r=self.payment(invoice,amount='500');self.assertEqual(r.status_code,201,r.content)
        from .workflow import eligible
        self.job.refresh_from_db();self.assertFalse(eligible(self.job),'Recorded funds alone must not unlock scheduling')
        self.assertEqual(self.act('attendance-request',preference='call').status_code,409)
        self.assertEqual(self.act('verify-deposit',confirmation='VERIFY').status_code,403)
        self.assertEqual(self.act('verify-deposit',user=self.ops,confirmation='VERIFY').status_code,200)
        self.assertEqual(DepositVerification.objects.count(),1)
        self.assertEqual(self.act('attendance-request',preference='call').status_code,200)
    def test_attendance_two_windows_and_idempotency(self):
        self.review();key=uuid.uuid4();self.job.refresh_from_db()
        url=reverse('workflow_action',args=[self.job.pk,'attendance-request'])
        v=dict(version=self.job.version,preference='date',date=str(timezone.localdate()+timedelta(days=3)),window='10:00–12:00')
        self.assertEqual(self.post(url,v,key).status_code,400)
        v['window']='09:00–13:00';self.assertEqual(self.post(url,v,key).status_code,200)
        self.assertEqual(self.post(url,v,key).status_code,200);self.assertEqual(self.job.attendance_requests.count(),1)
        self.assertEqual(self.job.attendance_requests.get().status,'pending')
    def test_completion_and_final_payment_closure(self):
        self.review();self.client.force_login(self.ops);self.assertEqual(self.invoice().status_code,400)
        self.assertEqual(self.act('completion',user=self.ops,report='Completed',before_unavailable=True,exception_reason='Unavailable').status_code,400)
        self.doc('completion_after')
        r=self.act('completion',user=self.ops,report='Completed',before_unavailable=True,exception_reason='Unavailable');self.assertEqual(r.status_code,200,r.content)
        self.assertEqual(CompletionRecord.objects.get().recorded_by,self.ops)
        from .maintenance import update_status
        self.job.refresh_from_db();self.job.status='attended';self.job.save(update_fields=['status'])
        self.assertEqual(update_status(self.ops,self.job,dict(status='completed',version=self.job.version)).status_code,200)
        self.client.force_login(self.ops);r=self.invoice();self.assertEqual(r.status_code,201,r.content)
        self.assertEqual(self.payment(r.json(),amount='1000').status_code,201)
        self.job.refresh_from_db();self.assertIsNotNone(self.job.closed_at);self.assertEqual(self.job.status,'closed')
        self.client.force_login(self.ops)
        invoice=self.client.get(self.detail_url).json()['invoices'][0]
        r=self.post(reverse('maintenance_invoice_adjustment',args=[self.job.pk,invoice['id'],'refunds']),dict(version=invoice['version'],payment_id=invoice['payments'][0]['id'],amount='100',refunded_on=str(timezone.localdate()),reason='Manual correction',reference='REFUND-TEST',confirmation='REFUND'))
        self.assertEqual(r.status_code,201,r.content)
        self.job.refresh_from_db();self.assertIsNone(self.job.closed_at);self.assertEqual(self.job.status,'completed')
    def test_private_comment_downloads_and_notifications(self):
        self.client.force_login(self.pm)
        r=self.client.post(reverse('maintenance_comment',args=[self.job.pk]),{'text':'Private PM instruction','visibility':'agency','attachments':fixtures.document()},HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(r.status_code,201,r.content);url=r.json()['attachments'][0]['download_url']
        for user,code in ((self.tenant,404),(self.foreign,404),(self.pm,200)):
            self.client.force_login(user);self.assertEqual(self.client.get(url).status_code,code)
        self.client.force_login(self.pm);self.assertIn('Private PM instruction',self.client.get(self.detail_url).content.decode())
        self.client.force_login(self.tenant);self.assertNotIn('Private PM instruction',self.client.get(self.detail_url).content.decode())
        self.assertFalse(UserJobNotification.objects.filter(user=self.tenant,event__kind='comment_added').exists())
    def test_scoped_stages_and_persistent_notifications(self):
        self.review();self.client.force_login(self.pm);r=self.client.get(reverse('workflow_stages')).json()
        self.assertEqual([s['label'] for s in r['stages']],['Needs Your Attention','New Requests','Awaiting Quote Approval','Awaiting Deposit','Booked','Work Underway','Awaiting Final Payment','Closed']);self.assertEqual(r['stages'][0]['count'],1);self.assertEqual(next(s['count'] for s in r['stages'] if s['key']=='booked'),0)
        n=self.client.get(reverse('workflow_notifications')).json()['results'][0]
        self.assertEqual(self.post(reverse('workflow_notification_read',args=[n['id']]),{'read':True}).status_code,200)
        self.client.force_login(self.foreign);self.assertEqual(self.client.get(reverse('workflow_stages')).json()['results'],[])
        self.assertEqual(self.post(reverse('workflow_notification_read',args=[n['id']]),{'read':True}).status_code,404)

from . import test_scheduling as scheduling_fixtures
from .models import AttendanceRequest,TeamAppointment,JobInvoice,User,OperationsNotification

@override_settings(**scheduling_fixtures.SETTINGS)
class AttendanceAndFinanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):scheduling_fixtures.fixtures(cls)
    setUp=scheduling_fixtures.SupplierTests.setUp
    def prepare(self):
        self.client.force_login(self.pm)
        def post(op,v):
            self.job.refresh_from_db()
            return self.client.post(reverse('workflow_action',args=[self.job.pk,op]),__import__('json').dumps(dict(version=self.job.version,**v)),content_type='application/json',HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        r=post('review',dict(job_type='callout',urgency='normal',access_responsibility='pm',limit='2000'));self.assertEqual(r.status_code,200,r.content)
        self.when=timezone.localdate()+timedelta(days=2)
        r=post('attendance-request',dict(preference='date',date=str(self.when),window='09:00–13:00'));self.assertEqual(r.status_code,200,r.content)
        self.arrival=AttendanceRequest.objects.get(request=self.job);self.job.refresh_from_db()
        self.client.force_login(self.ops)
        return dict(version=self.job.version,attendance=self.arrival.pk,date=str(self.when),window='09:00–13:00',subcontractor=str(self.partner.pk),team=str(self.crew.pk),starts_at=str(self.when)+'T09:00:00+02:00',ends_at=str(self.when)+'T10:00:00+02:00')
    def confirm(self,v,key=None):
        return self.client.post(reverse('workflow_confirm_attendance',args=[self.job.pk]),__import__('json').dumps(v),content_type='application/json',HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))
    def test_confirm_booking_keeps_private_duration_separate_and_notifies_both(self):
        v=self.prepare();key=uuid.uuid4();r=self.confirm(v,key);self.assertEqual(r.status_code,201,r.content)
        self.assertEqual(self.confirm(v,key).status_code,200);self.assertEqual(TeamAppointment.objects.count(),1)
        self.arrival.refresh_from_db();self.assertEqual(self.arrival.agreed_window,'09:00–13:00')
        self.client.force_login(self.pm)
        response=self.client.get(reverse('customer_portal_section',args=['calendar']),{'week':str(self.when)});self.assertEqual(response.status_code,200,response.content)
        row=response.json()['appointments'][0];self.assertIn('13:00',row['ends_at']);self.assertNotIn('PRIVATE',str(row));self.assertNotIn('subcontractor',row)
        self.assertTrue(UserJobNotification.objects.filter(user=self.tenant,event__details__action='Attendance confirmed').exists())
        stages=self.client.get(reverse('workflow_stages')).json()['stages']
        self.assertEqual(next(s['count'] for s in stages if s['key']=='booked'),1)
        self.assertEqual(len(self.client.get(reverse('workflow_stages')).json()['upcoming']),1)
        MaintenanceRequest.objects.filter(pk=self.job.pk).update(status='completed')
        self.assertEqual(self.client.get(reverse('workflow_stages')).json()['upcoming'],[])
    def test_alternative_requires_contact_confirmation_on_server(self):
        v=self.prepare();v.update(date=str(self.when+timedelta(days=1)),starts_at=str(self.when+timedelta(days=1))+'T12:00:00+02:00',ends_at=str(self.when+timedelta(days=1))+'T14:00:00+02:00',window='12:00–17:00')
        self.assertEqual(self.confirm(v).status_code,400);self.assertEqual(TeamAppointment.objects.count(),0)
        v.update(client_confirmed=True,contact_category='tenant');r=self.confirm(v);self.assertEqual(r.status_code,201,r.content)
        self.arrival.refresh_from_db();self.assertEqual(self.arrival.requested_date,self.when);self.assertEqual(self.arrival.agreed_date,self.when+timedelta(days=1));self.assertEqual(self.arrival.confirmed_by,self.ops)
    def test_direct_scheduling_cannot_bypass_attendance_confirmation(self):
        self.prepare()
        body=scheduling_fixtures.data(self.job,self.partner,self.crew,day=self.when)
        self.assertEqual(scheduling_fixtures.save(self.client,body).status_code,409)
    def test_supplier_invoice_next_monday_private_finance_and_persistent_overdue_alert(self):
        self.prepare()
        from .test_regions import assign
        self.job.refresh_from_db()
        response=self.client.post(reverse('operations_assignments',args=[self.job.pk]),__import__('json').dumps(dict(version=self.job.version,subcontractor=str(self.partner.pk),team=str(self.crew.pk),submission_key=str(uuid.uuid4()))),content_type='application/json')
        self.assertEqual(response.status_code,201,response.content)
        r=self.client.post(reverse('maintenance_invoice',args=[self.job.pk]),dict(number='SUPPLIER-MANUAL',amount='500',due_date=str(timezone.localdate()),subcontractor=str(self.partner.pk),attachments=fixtures.document()),HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(r.status_code,201,r.content);invoice=JobInvoice.objects.get()
        today=timezone.localdate();self.assertEqual(invoice.due_date,today+timedelta(days=(7-today.weekday())%7 or 7))
        self.client.force_login(self.finance);self.assertEqual(self.client.get(reverse('operations_monday_payments')).status_code,403)
        self.client.force_login(self.tenant);self.assertEqual(self.client.get(reverse('maintenance_invoice_pdf',args=[self.job.pk,invoice.pk])).status_code,403)
        JobInvoice.objects.filter(pk=invoice.pk).update(due_date=today-timedelta(days=1))
        from .workflow import refresh_overdue
        refresh_overdue(self.ops);refresh_overdue(self.ops)
        self.assertEqual(UserJobNotification.objects.filter(event__dedup_key__startswith='supplier-overdue:').count(),1)

from django.test import TransactionTestCase,skipUnlessDBFeature
from . import test_financial75 as concurrent_fixtures
from .models import JobQuotation,DocumentSequence,MaintenanceAttachment

@override_settings(SECURE_SSL_REDIRECT=False,ALLOWED_HOSTS=['testserver'])
class OperationalConcurrencyTests(TransactionTestCase):
    setUp=concurrent_fixtures.FinancialConcurrencyTests.setUp
    race=concurrent_fixtures.FinancialConcurrencyTests.race
    api=concurrent_fixtures.FinancialConcurrencyTests.api
    @skipUnlessDBFeature('has_select_for_update')
    def test_simultaneous_callout_authorisations_allocate_once(self):
        url=reverse('workflow_action',args=[self.job.pk,'review'])
        body=dict(version=1,job_type='callout',urgency='urgent',access_responsibility='pm',limit='1000')
        self.assertEqual(sorted(self.race([lambda c:self.api(c,url,body)]*2,user=self.pm)),[200,409])
        self.job.refresh_from_db();self.assertEqual(self.job.job_number,1);self.assertEqual(WorkflowDecision.objects.count(),1)
    @skipUnlessDBFeature('has_select_for_update')
    def test_callout_and_quoted_approvals_share_one_global_sequence(self):
        other=MaintenanceRequest.objects.create(property=self.home,reported_by=self.ops,title='Quoted',description='Synthetic',category='Plumbing',job_type='quoted',workflow_version=1)
        file=MaintenanceAttachment.objects.create(request=other,uploaded_by=self.ops,purpose='quotation',visibility='internal',storage_key=f'maintenance/{other.pk}/{uuid.uuid4()}.pdf',filename='quote.pdf',content_type='application/pdf',size=1,sha256='a'*64)
        quote=JobQuotation.objects.create(request=other,document=file,created_by=self.ops,reference='SQ-PG-MANUAL',creation_key=uuid.uuid4(),title='Sent',amount='1000',status='sent')
        review=reverse('workflow_action',args=[self.job.pk,'review']);decision=reverse('maintenance_quote_decision',args=[other.pk,quote.pk])
        results=self.race([lambda c:self.api(c,review,dict(version=1,job_type='callout',urgency='normal',access_responsibility='sevlink',limit='1000')),lambda c:self.api(c,decision,dict(version=1,status='approved',reason='Approved'))],user=self.pm)
        self.assertEqual(results,[200,200]);self.job.refresh_from_db();other.refresh_from_db()
        self.assertEqual({self.job.job_number,other.job_number},{1,2})
        self.assertEqual(DocumentSequence.objects.get(prefix='SV',year=0).last_value,2)
    @skipUnlessDBFeature('has_select_for_update')
    def test_concurrent_additional_decisions_preserve_approved_limit_and_audit(self):
        self.client.force_login(self.pm)
        url=reverse('workflow_action',args=[self.job.pk,'review'])
        result=self.api(self.client,url,dict(version=1,job_type='callout',urgency='normal',access_responsibility='pm',limit='1000'));self.assertEqual(result,200)
        self.job.refresh_from_db()
        first=AdditionalAuthorisation.objects.create(request=self.job,amount='1500',reason='First increase',requested_by=self.ops)
        second=AdditionalAuthorisation.objects.create(request=self.job,amount='2000',reason='Second increase',requested_by=self.ops)
        url=reverse('workflow_action',args=[self.job.pk,'additional-decision']);version=self.job.version
        result=self.race([lambda c:self.api(c,url,dict(version=version,additional=first.pk,decision='approved')),lambda c:self.api(c,url,dict(version=version,additional=second.pk,decision='approved'))],user=self.pm)
        self.assertEqual(sorted(result),[200,409]);self.assertEqual(AdditionalAuthorisation.objects.filter(status='approved').count(),1)
        self.assertEqual(WorkflowDecision.objects.filter(operation='additional-decision').count(),1)


@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False)
class PMDashboardAdjustmentTests(TestCase):
    setUpTestData=OperationalWorkflowTests.__dict__['setUpTestData']
    setUp=OperationalWorkflowTests.setUp
    post=OperationalWorkflowTests.post
    act=OperationalWorkflowTests.act
    review=OperationalWorkflowTests.review
    def test_unique_attention_jobs_confirmed_booking_and_operations_stages(self):
        self.review()
        AdditionalAuthorisation.objects.create(request=self.job,amount='2000',reason='Additional work',requested_by=self.ops)
        self.client.force_login(self.pm)
        url=reverse('workflow_stages')
        data=self.client.get(url).json()
        self.assertEqual(len(data['stages']),8)
        self.assertGreaterEqual(data['attention_action_count'],2)
        self.assertEqual(data['stages'][0]['count'],1)
        attention_jobs=self.client.get(url,{'stage':'attention'}).json()['results']
        self.assertEqual(len(attention_jobs),1)
        reasons=attention_jobs[0]['attention_actions']
        self.assertEqual(len(reasons),data['attention_action_count'])
        self.assertIn('Additional-work authorisation required',[a['action'] for a in reasons])
        self.assertIn('Please confirm attendance date',[a['action'] for a in reasons])
        self.assertNotIn('requested_by',str(reasons))
        self.assertEqual(self.client.get(url,{'stage':'booked'}).json()['results'],[])
        self.act('attendance-request',preference='date',date=str(timezone.localdate()+timedelta(days=3)),window='09:00–13:00')
        self.assertEqual(self.client.get(url,{'stage':'booked'}).json()['results'],[])
        self.job.status='completed';self.job.save(update_fields=['status'])
        self.job.additional_authorisations.update(status='declined')
        self.assertEqual(self.client.get(url).json()['stages'][0]['count'],0)
        self.client.force_login(self.foreign)
        self.assertTrue(all(s['count']==0 for s in self.client.get(url).json()['stages']))
        self.client.force_login(self.admin)
        self.assertEqual(len(self.client.get(url).json()['stages']),8)
        self.client.force_login(self.ops)
        operations=self.client.get(url).json()
        self.assertEqual(len(operations['stages']),10)
        self.assertEqual([item['label'] for item in operations['summary']],['New today','Urgent attention','Visits today','Waiting on Sevlink'])
        self.assertEqual(operations['summary'][0]['count'],1)

    def test_real_register_filters_search_beyond_first_page_and_number_references(self):
        for i in range(51):
            target=MaintenanceRequest.objects.create(property=self.home,reported_by=self.tenant,title='Target across pages' if i==50 else f'Other repair {i}',description='Synthetic',category='Plumbing',urgency='high' if i==50 else 'normal')
        self.client.force_login(self.pm)
        url=reverse('maintenance_collection')
        result=self.client.get(url,dict(register='1',search=target.request_reference,property=str(self.home.pk),category='Plumbing',urgency='high',bucket='open',sort='oldest')).json()
        self.assertEqual(result['count'],1);self.assertEqual(result['results'][0]['id'],str(target.pk));self.assertEqual(result['register']['total_count'],52)
        result=self.client.get(url,dict(register='1',page=2,sort='oldest')).json()
        self.assertEqual(result['count'],52);self.assertEqual(len(result['results']),2)
        self.assertIn(str(target.pk),[j['id'] for j in result['results']])

    def test_register_facets_counts_and_filters_cannot_broaden_portfolio(self):
        from .models import Property
        other=Property.objects.create(agency=self.foreign_agency,manager=self.foreign,name='Foreign private property',address='Foreign private address')
        MaintenanceRequest.objects.create(property=other,reported_by=self.foreign,title='Foreign private job',description='Synthetic',category='Electrical')
        self.client.force_login(self.pm);url=reverse('maintenance_collection')
        result=self.client.get(url,dict(register='1')).json()
        self.assertEqual(result['count'],1);self.assertNotIn('Foreign private',str(result));self.assertEqual(result['register']['agencies'],[])
        self.assertEqual(self.client.get(url,dict(register='1',agency=str(self.foreign_agency.pk))).json()['count'],0)
        self.assertEqual(self.client.get(url,dict(register='1',property='bad-id')).status_code,400)
        self.client.force_login(self.cotenant);self.assertEqual(self.client.get(url,dict(register='1')).json()['count'],0)
        self.client.force_login(self.ops);self.assertEqual(self.client.get(url,dict(register='1')).json()['count'],2)
        self.assertEqual(self.client.get(url,dict(register='1',stage='new')).json()['count'],2)
        self.assertEqual(self.client.get(url,dict(register='1',stage='approval')).json()['count'],0)
