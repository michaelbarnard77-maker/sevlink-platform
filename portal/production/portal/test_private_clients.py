import re
import uuid
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from . import test_notifications as fixtures
from .models import (PrivateClient, PrivateClientLink, MaintenanceRequest, MailQueue,
                     JobQuotation, QuotationAction, User, Membership, InvoicePayment)
from .test_attachments import document, photo
from .workflow import pipeline_for, pipeline_stage, eligible


@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False,ALLOWED_HOSTS=['testserver'],SITE_URL='http://testserver',SMTP_DELIVERY_ENABLED=False,OPERATIONS_LIVE_DELIVERY_ENABLED=False)
class PrivateClientTests(TestCase):
    setUpTestData=classmethod(fixtures.EventWorkflowTests.setUpTestData.__func__)
    post=fixtures.EventWorkflowTests.post

    def setUp(self):
        fixtures.EventWorkflowTests.setUp(self)

    def create(self,kind='quoted',email='private-client@example.test',key=None,user=None):
        self.client.force_login(user or self.ops)
        result=self.post(reverse('private_client_create'),dict(name='Private Customer',email=email,phone='082 000 1234',address='7 Sample Street',title='Kitchen maintenance',description='Sample private work',job_type=kind,**({'limit':'2000','authorisation':'Client authorised by phone for up to R2000.'} if kind=='callout' else {})),key)
        if result.status_code==201:
            self.job=MaintenanceRequest.objects.get(pk=result.json()['id']);self.customer=self.job.private_client
        return result

    def quote(self,reference='PRIVATE-Q-1'):
        self.client.force_login(self.ops)
        result=self.client.post(reverse('maintenance_quote',args=[self.job.pk]),dict(reference=reference,title='Private quotation',scope='Repair and test the kitchen pipe.',amount='2000',attachments=document()),HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(result.status_code,201,result.content);q=result.json()
        result=self.post(reverse('maintenance_quote_action',args=[self.job.pk,q['id'],'send']),{'version':q['version']})
        self.assertEqual(result.status_code,200,result.content)
        return JobQuotation.objects.get(pk=q['id'])

    def link(self,purpose,quote=None):
        qs=PrivateClientLink.objects.filter(client=self.customer,purpose=purpose,revoked_at=None)
        if quote:qs=qs.filter(quotation=quote)
        link=qs.latest('created_at');token=re.search(r'/client/link/([^/]+)/',link.message.body).group(1)
        return link,token

    def accept(self):
        q=self.quote();link,token=self.link('quote',q)
        browser=Client();result=browser.post(reverse('private_client_link',args=[token]),{'decision':'approved'})
        self.assertEqual(result.status_code,200,result.content);self.job.refresh_from_db()
        return q

    def activate(self):
        link,token=self.link('activate');browser=Client()
        result=browser.post(reverse('private_client_link',args=[token]),{'new_password1':'Private-Portal!2026-safe','new_password2':'Private-Portal!2026-safe'})
        self.assertEqual(result.status_code,302,result.content)
        self.customer.refresh_from_db();self.customer.user.refresh_from_db()
        return browser,token

    def test_private_quote_get_and_pdf_do_not_accept_or_activate(self):
        self.assertEqual(self.create().status_code,201)
        q=self.quote();link,token=self.link('quote',q);browser=Client()
        self.assertEqual(browser.get(reverse('private_client_link',args=[token])).status_code,200)
        self.assertEqual(browser.get(reverse('private_client_pdf',args=[token])).status_code,200)
        q.refresh_from_db();self.assertEqual(q.status,'sent');self.assertFalse(self.customer.user.is_active)
        self.assertFalse(PrivateClientLink.objects.filter(purpose='activate').exists())
        self.assertNotEqual(token,link.token_hash)
        self.assertEqual(browser.get(reverse('private_client_link',args=['invalid-token'])).status_code,410)
        self.assertEqual(pipeline_for(self.job),'quotes')

    def test_accept_once_then_activate_and_follow_payment_gate(self):
        self.create();q=self.accept();q.refresh_from_db();self.assertEqual(q.status,'approved')
        self.assertFalse(self.customer.user.is_active);self.assertEqual(pipeline_for(self.job),'jobs');self.assertEqual(pipeline_stage(self.job,'jobs'),'new');self.assertFalse(eligible(self.job))
        link,token=self.link('quote',q)
        self.assertEqual(Client().post(reverse('private_client_link',args=[token]),{'decision':'rejected'}).status_code,200)
        self.assertEqual(QuotationAction.objects.filter(quote=q,kind='approved').count(),1)
        self.assertEqual(PrivateClientLink.objects.filter(purpose='activate').count(),1)
        browser,activation=self.activate()
        self.assertTrue(self.customer.user.is_active);self.assertTrue(self.customer.portal_active)
        self.assertEqual(browser.get(reverse('private_client_portal')).status_code,200)
        self.assertEqual(browser.get(reverse('maintenance_context')).json()['user']['role'],'client')
        denied=browser.post(reverse('workflow_action',args=[self.job.pk,'attendance-request']),{'version':self.job.version,'preference':'call'},content_type='application/json',HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(denied.status_code,409)
        self.assertEqual(Client().get(reverse('private_client_link',args=[activation])).status_code,410)
        self.client.force_login(self.ops)
        result=self.post(reverse('workflow_action',args=[self.job.pk,'jobs-intake']),dict(version=self.job.version,decision='without_deposit'))
        self.assertEqual(result.status_code,200,result.content);self.job.refresh_from_db();self.assertTrue(eligible(self.job))
        self.assertTrue(MailQueue.objects.filter(recipient=self.customer.email,subject__icontains='preferred attendance').exists())

    def test_decline_stays_quotes_and_does_not_create_active_portal(self):
        self.create();q=self.quote();link,token=self.link('quote',q)
        result=Client().post(reverse('private_client_link',args=[token]),{'decision':'rejected','reason':'Not proceeding'})
        self.assertEqual(result.status_code,200);q.refresh_from_db();self.assertEqual(q.status,'rejected')
        self.assertEqual(pipeline_for(self.job),'quotes');self.assertFalse(self.customer.user.is_active)
        self.assertFalse(PrivateClientLink.objects.filter(purpose='activate').exists())

    def test_callout_activates_immediately_and_client_can_request_date(self):
        self.assertEqual(self.create('callout').status_code,201)
        self.assertEqual(pipeline_for(self.job),'jobs');self.assertEqual(pipeline_stage(self.job,'jobs'),'ready');self.assertTrue(eligible(self.job))
        browser,_=self.activate()
        result=browser.post(reverse('workflow_action',args=[self.job.pk,'attendance-request']),{'version':self.job.version,'preference':'call'},content_type='application/json',HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(result.status_code,200,result.content)
        self.assertEqual(self.job.attendance_requests.get().requested_by_id,self.customer.user_id)

    def test_client_can_report_paid_comment_and_not_record_money(self):
        self.create('callout');browser,_=self.activate()
        self.client.force_login(self.ops)
        from .models import CompletionRecord
        uploaded=self.client.post(reverse('workflow_documents',args=[self.job.pk]),{'kind':'completion_after','attachments':photo()})
        self.assertEqual(uploaded.status_code,201,uploaded.content)
        report=CompletionRecord.objects.create(request=self.job,recorded_by=self.ops,report='Completed private call-out.',before_unavailable=True,exception_reason='Sample before photo unavailable.')
        report.documents.add(self.job.attachments.get(purpose='completion_after'))
        self.job.status='completed';self.job.save(update_fields=['status'])
        result=self.client.post(reverse('maintenance_invoice',args=[self.job.pk]),dict(number='PRIVATE-INV',purpose='final',visibility='shared',amount='2000',due_date=str(timezone.localdate()),attachments=document()),HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(result.status_code,201,result.content);inv=result.json()
        paid=browser.post(reverse('maintenance_invoice_report_paid',args=[self.job.pk,inv['id']]),{'version':inv['version']},content_type='application/json',HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(paid.status_code,201,paid.content);self.assertEqual(InvoicePayment.objects.count(),0)
        comment=browser.post(reverse('maintenance_comment',args=[self.job.pk]),{'text':'Payment sent; please check.','visibility':'shared'},content_type='application/json',HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(comment.status_code,201,comment.content)
        self.assertEqual(browser.get(reverse('maintenance_invoice_pdf',args=[self.job.pk,inv['id']])).status_code,200)
        self.assertEqual(browser.post(reverse('maintenance_invoice_verify',args=[self.job.pk,inv['id']]),{'version':inv['version']},content_type='application/json').status_code,403)

    def test_multi_job_access_closes_only_after_last_job_then_reactivates_same_record(self):
        self.create('callout');first=self.job;browser,_=self.activate();user_id=self.customer.user_id;client_id=self.customer.pk
        self.create('callout');second=self.job
        first.closed_at=timezone.now();first.status='closed';first.save(update_fields=['closed_at','status'])
        self.customer.refresh_from_db();self.assertTrue(self.customer.portal_active)
        self.assertEqual(browser.get(reverse('private_client_portal')).status_code,200)
        second.closed_at=timezone.now();second.status='closed';second.save(update_fields=['closed_at','status'])
        self.customer.refresh_from_db();self.customer.user.refresh_from_db();self.assertFalse(self.customer.portal_active);self.assertFalse(self.customer.user.is_active)
        self.assertEqual(browser.get(reverse('private_client_portal')).status_code,302)
        self.assertEqual(MaintenanceRequest.objects.filter(private_client_id=client_id).count(),2)
        self.create('callout');self.assertEqual(self.customer.pk,client_id);self.assertEqual(self.customer.user_id,user_id)
        fresh,_=self.activate();self.assertEqual(fresh.get(reverse('maintenance_collection')).json()['count'],3)

    def test_client_isolation_roles_and_replaced_links(self):
        self.create();old=self.quote();link,token=self.link('quote',old)
        self.quote('PRIVATE-Q-2')
        self.assertEqual(Client().get(reverse('private_client_link',args=[token])).status_code,410)
        self.assertEqual(Client().get(reverse('private_client_pdf',args=[token])).status_code,410)
        self.client.force_login(self.pm);self.assertEqual(self.post(reverse('private_client_create'),{}).status_code,403)
        self.create('callout',email='second-private@example.test');other,_=self.activate()
        self.assertEqual(other.get(reverse('maintenance_detail',args=[old.request_id])).status_code,404)
        self.assertEqual(other.get(reverse('maintenance_collection')).json()['count'],1)
        self.assertEqual(other.post(reverse('private_client_create'),{},content_type='application/json').status_code,403)

    def test_csrf_and_expired_links_are_not_accepted(self):
        self.create();q=self.quote();link,token=self.link('quote',q)
        browser=Client(enforce_csrf_checks=True);url=reverse('private_client_link',args=[token]);response=browser.get(url)
        self.assertEqual(response['Referrer-Policy'],'same-origin')
        self.assertEqual(browser.post(url,{'decision':'approved'}).status_code,403)
        link.expires_at=timezone.now();link.save(update_fields=['expires_at'])
        self.assertEqual(Client().get(url).status_code,410)
        q.refresh_from_db();self.assertEqual(q.status,'sent')

    def test_existing_agency_email_is_not_merged_or_changed(self):
        before=self.pm.is_active
        result=self.create(email=self.pm.email)
        self.assertEqual(result.status_code,400)
        self.pm.refresh_from_db();self.assertEqual(self.pm.is_active,before)
        self.assertEqual(Membership.objects.get(user=self.pm).role,'pm')
        self.assertEqual(PrivateClient.objects.count(),0)
