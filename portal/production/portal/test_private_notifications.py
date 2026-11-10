import json
import uuid
from django.test import TestCase,override_settings
from django.urls import reverse
from django.utils import timezone
from . import test_private_clients as fixtures
from .models import MaintenanceRequest,MaintenanceAttachment,JobInvoice,UserJobNotification
from .events import record

@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False,ALLOWED_HOSTS=['testserver'],SITE_URL='http://testserver',SMTP_DELIVERY_ENABLED=False,OPERATIONS_LIVE_DELIVERY_ENABLED=False)
class PrivateNotificationTests(TestCase):
    setUpTestData=classmethod(fixtures.PrivateClientTests.setUpTestData.__func__)
    create=fixtures.PrivateClientTests.create
    quote=fixtures.PrivateClientTests.quote
    accept=fixtures.PrivateClientTests.accept
    activate=fixtures.PrivateClientTests.activate
    link=fixtures.PrivateClientTests.link
    post=fixtures.PrivateClientTests.post

    def setUp(self):
        fixtures.PrivateClientTests.setUp(self)
        self.assertEqual(self.create().status_code,201)
        self.accept();self.browser,_=self.activate()
        self.url=reverse('private_client_notifications')

    def badge(self,key):return self.browser.get(self.url).json()['counts'][key]

    def comment(self,text='New customer update'):
        self.client.force_login(self.ops)
        response=self.post(reverse('maintenance_comment',args=[self.job.pk]),{'text':text,'visibility':'shared'})
        self.assertEqual(response.status_code,201,response.content)
        return UserJobNotification.objects.filter(user=self.customer.user,event__request=self.job,event__kind='comment_added').latest('pk')

    def acknowledge(self,section,ids,job=None):
        return self.browser.post(self.url,json.dumps({'job':str(job or self.job.pk),'section':section,'notifications':ids}),content_type='application/json')

    def test_new_comments_count_clear_only_when_viewed_and_never_clear_a_later_comment(self):
        first=self.comment()
        self.assertEqual(self.badge('comments'),1)
        first.refresh_from_db();self.assertIsNone(first.read_at)
        second=self.comment('A later update')
        response=self.acknowledge('comments',[first.pk])
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['counts']['comments'],1)
        second.refresh_from_db();self.assertIsNone(second.read_at)
        self.assertEqual(self.acknowledge('comments',[second.pk]).json()['counts']['comments'],0)
        self.assertEqual(self.acknowledge('comments',[second.pk]).json()['counts']['comments'],0)

    def test_own_comments_do_not_count_and_other_sections_are_not_marked_read(self):
        notice=self.comment()
        self.assertEqual(self.acknowledge('invoices',[notice.pk]).json()['counts']['comments'],1)
        self.assertEqual(self.browser.post(reverse('maintenance_comment',args=[self.job.pk]),json.dumps({'text':'My own reply','visibility':'shared'}),content_type='application/json',HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())).status_code,201)
        self.assertEqual(self.badge('comments'),1)

    def test_invoice_badge_does_not_double_count_and_clears_after_paid_report(self):
        document=MaintenanceAttachment.objects.create(request=self.job,uploaded_by=self.ops,purpose='invoice',storage_key='badge-invoice',filename='invoice.pdf',content_type='application/pdf',size=10,sha256='a'*64)
        invoice=JobInvoice.objects.create(request=self.job,document=document,uploaded_by=self.ops,number='BADGE-INV',amount=100,due_date=timezone.localdate(),creation_key=uuid.uuid4(),purpose='deposit',visibility='shared')
        event=record(self.job,self.ops,'invoice_uploaded','test-invoice:'+str(uuid.uuid4()),{'invoice_id':str(invoice.pk),'number':invoice.number,'amount':'100','status':'unpaid'})
        notice=UserJobNotification.objects.get(user=self.customer.user,event=event)
        self.assertEqual(self.badge('invoices'),1)
        self.assertEqual(self.acknowledge('invoices',[notice.pk]).json()['counts']['invoices'],1)
        result=self.browser.post(reverse('maintenance_invoice_report_paid',args=[self.job.pk,invoice.pk]),json.dumps({'version':invoice.version}),content_type='application/json',HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(result.status_code,201,result.content)
        self.assertEqual(self.badge('invoices'),0)

    def test_pending_quote_badge_remains_after_viewing_until_decision(self):
        self.create(email=self.customer.email)
        quote=self.quote(reference='BADGE-Q')
        notice=UserJobNotification.objects.get(user=self.customer.user,event__request=self.job,event__kind='quote_sent')
        self.assertEqual(self.badge('quotes'),1)
        self.assertEqual(self.acknowledge('quotes',[notice.pk]).json()['counts']['quotes'],1)
        result=self.browser.post(reverse('maintenance_quote_decision',args=[self.job.pk,quote.pk]),json.dumps({'version':quote.version,'status':'approved'}),content_type='application/json',HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(result.status_code,200,result.content)
        self.assertEqual(self.badge('quotes'),0)

    def test_other_jobs_and_other_roles_cannot_read_or_acknowledge_private_badges(self):
        foreign=MaintenanceRequest.objects.create(property=self.home,reported_by=self.tenant,title='Other agency job',description='Private',category='Painting')
        event=record(foreign,self.ops,'status_changed','foreign:'+str(uuid.uuid4()),{'status':'reviewed'})
        notice=UserJobNotification.objects.create(user=self.customer.user,event=event)
        result=self.browser.get(self.url)
        self.assertNotIn(str(foreign.pk),result.json()['jobs'])
        self.assertEqual(self.acknowledge('jobs',[notice.pk],job=foreign.pk).status_code,404)
        notice.refresh_from_db();self.assertIsNone(notice.read_at)
        self.client.force_login(self.pm)
        self.assertEqual(self.client.get(self.url).status_code,403)
        self.assertEqual(self.acknowledge('comments',[True]).status_code,400)

    def test_attendance_action_is_badged_until_preference_is_submitted(self):
        from datetime import timedelta
        self.create(kind='callout',email=self.customer.email)
        self.assertEqual(self.badge('attendance'),1)
        self.assertEqual(self.acknowledge('attendance',[]).json()['counts']['attendance'],1)
        self.job.refresh_from_db()
        result=self.browser.post(reverse('workflow_action',args=[self.job.pk,'attendance-request']),json.dumps({'version':self.job.version,'preference':'date','date':str(timezone.localdate()+timedelta(days=2)),'window':'09:00–13:00'}),content_type='application/json',HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(result.status_code,200,result.content)
        self.assertEqual(self.badge('attendance'),0)

    def test_message_email_deep_link_opens_the_messages_section(self):
        from .models import MailQueue
        self.comment()
        message=MailQueue.objects.filter(recipient=self.customer.email,subject='Sevlink new message').latest('pk')
        self.assertIn('section=comments',message.body)
