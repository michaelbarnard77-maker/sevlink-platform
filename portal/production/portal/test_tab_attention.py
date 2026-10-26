"""Real business actions and recipient-specific tab attention; no browser-local state."""
import uuid
from django.test import TestCase, override_settings
from django.urls import reverse
from . import test_operational_workflow as workflows
from .models import JobActivity, UserJobNotification


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class TabAttentionTests(TestCase):
    setUpTestData=classmethod(workflows.OperationalWorkflowTests.setUpTestData.__func__)
    setUp=workflows.OperationalWorkflowTests.setUp
    post=workflows.OperationalWorkflowTests.post
    act=workflows.OperationalWorkflowTests.act
    review=workflows.OperationalWorkflowTests.review
    quote=workflows.OperationalWorkflowTests.quote
    invoice=workflows.OperationalWorkflowTests.invoice
    payment=workflows.OperationalWorkflowTests.payment
    doc=workflows.OperationalWorkflowTests.doc

    def tabs(self,user):
        self.client.force_login(user)
        result=self.client.get(self.detail_url)
        self.assertEqual(result.status_code,200,result.content)
        return result.json()['tab_attention']

    def read(self,user,notification):
        self.client.force_login(user)
        return self.post(reverse('workflow_notification_read',args=[notification]),{'read':True})

    def comment(self,user,visibility,text='Synthetic tab notification'):
        self.client.force_login(user)
        result=self.post(reverse('maintenance_comment',args=[self.job.pk]),{'text':text,'visibility':visibility})
        self.assertEqual(result.status_code,201,result.content)
        return result.json()

    def test_quote_decision_and_invoice_settlement_clear_actions_not_merely_reading(self):
        self.review('quoted');self.client.force_login(self.ops)
        q=self.quote(reference='SQ-TAB-001').json()
        sent=self.post(reverse('maintenance_quote_action',args=[self.job.pk,q['id'],'send']),{'version':q['version']}).json()
        for user in (self.pm,self.admin):self.assertEqual(self.tabs(user)['counts']['quotes'],1)
        for notice in self.tabs(self.pm)['unread']['quotes']:self.assertEqual(self.read(self.pm,notice).status_code,200)
        self.assertEqual(self.tabs(self.pm)['counts']['quotes'],1)
        self.client.force_login(self.pm)
        decision=self.post(reverse('maintenance_quote_decision',args=[self.job.pk,q['id']]),{'version':sent['version'],'status':'approved','reason':'Approved test'})
        self.assertEqual(decision.status_code,200,decision.content)
        self.assertEqual(self.tabs(self.pm)['counts']['quotes'],0)
        self.client.force_login(self.ops)
        response=self.invoice(purpose='deposit');self.assertEqual(response.status_code,201,response.content)
        invoice=response.json()
        self.assertEqual(self.tabs(self.pm)['counts']['invoices'],1)
        for notice in self.tabs(self.pm)['unread']['invoices']:self.read(self.pm,notice)
        self.assertEqual(self.tabs(self.pm)['counts']['invoices'],1)
        self.client.force_login(self.ops)
        response=self.payment(invoice,amount='500');self.assertEqual(response.status_code,201,response.content)
        self.assertEqual(self.tabs(self.pm)['counts']['invoices'],1)
        self.client.force_login(self.ops)
        invoice=self.client.get(self.detail_url).json()['invoices'][0]
        response=self.payment(invoice,amount='500');self.assertEqual(response.status_code,201,response.content)
        self.assertEqual(self.tabs(self.pm)['counts']['invoices'],0)

    def test_comment_visibility_read_state_and_foreign_notification_permissions(self):
        self.comment(self.ops,'shared')
        self.comment(self.ops,'agency','PRIVATE AGENCY DISCUSSION')
        self.comment(self.ops,'internal','PRIVATE SUPPLIER NOTE')
        self.assertEqual(self.tabs(self.pm)['counts']['comments'],2)
        self.assertEqual(self.tabs(self.tenant)['counts']['comments'],1)
        self.assertEqual(self.tabs(self.ops)['counts']['comments'],0,'Do not badge own messages')
        self.comment(self.pm,'agency','Own message should not require my attention')
        self.assertEqual(self.tabs(self.pm)['counts']['comments'],2)
        actions=self.client.get(reverse('customer_portal_section',args=['attention'])).json()['items']
        self.assertEqual([a['action'] for a in actions if a['key'].startswith('comments:')],['Unread job comments (2)'])
        notice=self.tabs(self.pm)['unread']['comments'][0]
        self.assertEqual(self.read(self.foreign,notice).status_code,404)
        self.assertEqual(self.tabs(self.pm)['counts']['comments'],2)
        for notice in self.tabs(self.pm)['unread']['comments']:self.read(self.pm,notice)
        self.assertEqual(self.tabs(self.pm)['counts']['comments'],0)
        self.assertEqual(self.tabs(self.tenant)['counts']['comments'],1,'Read state belongs to each recipient')
        self.client.force_login(self.foreign)
        self.assertEqual(self.client.get(self.detail_url).status_code,404)
        self.job.tenant_comments_allowed=False;self.job.save(update_fields=['tenant_comments_allowed'])
        self.assertEqual(self.tabs(self.tenant)['counts']['comments'],0)

    def test_internal_invoice_counts_cannot_leak_even_with_misdirected_notice(self):
        self.job.workflow_version=0;self.job.save(update_fields=['workflow_version'])
        self.client.force_login(self.ops)
        response=self.invoice(visibility='internal',number='PRIVATE-SUPPLIER-PDF')
        self.assertEqual(response.status_code,201,response.content)
        event=JobActivity.objects.get(kind='invoice_uploaded',request=self.job)
        UserJobNotification.objects.get_or_create(user=self.pm,event=event)
        UserJobNotification.objects.get_or_create(user=self.tenant,event=event)
        self.assertEqual(self.tabs(self.ops)['counts']['costs'],1)
        pm=self.tabs(self.pm);tenant=self.tabs(self.tenant)
        self.assertEqual(pm['counts']['invoices'],0)
        self.assertEqual(pm['unread']['invoices'],[])
        self.assertNotIn('costs',str(pm))
        self.assertNotIn('costs',str(tenant))
        self.assertNotIn('invoices',str(tenant))
        self.assertNotIn('quotes',str(tenant))

    def test_completed_report_notice_persists_and_reading_does_not_change_job(self):
        self.review();self.doc('completion_after');self.doc('completion_before')
        response=self.act('completion',user=self.ops,report='Accepted test report',before_unavailable=False)
        self.assertEqual(response.status_code,200,response.content)
        before=self.job.status
        pm=self.tabs(self.pm);tenant=self.tabs(self.tenant)
        self.assertEqual(pm['counts']['reports'],1);self.assertEqual(tenant['counts']['reports'],1)
        self.assertEqual(self.tabs(self.pm)['counts']['reports'],1,'GET does not mark notifications read')
        for notice in pm['unread']['reports']:self.read(self.pm,notice)
        self.assertEqual(self.tabs(self.pm)['counts']['reports'],0)
        self.assertEqual(self.tabs(self.tenant)['counts']['reports'],1)
        self.job.refresh_from_db();self.assertEqual(self.job.status,before)

    def test_attendance_action_remains_until_request_and_does_not_double_count_notice(self):
        self.review()
        tabs=self.tabs(self.pm)
        self.assertEqual(tabs['counts']['attendance'],1)
        for notice in tabs['unread']['attendance']:self.read(self.pm,notice)
        self.assertEqual(self.tabs(self.pm)['counts']['attendance'],1)
        response=self.act('attendance-request',preference='call');self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(self.tabs(self.pm)['counts']['attendance'],0)
        self.assertEqual(self.tabs(self.ops)['counts']['attendance'],1)
