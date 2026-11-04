import uuid
from decimal import Decimal
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from . import test_notifications as fixtures
from .models import MaintenanceRequest, WorkflowDecision, SchedulingArrangement, DepositVerification
from .test_attachments import document
from .workflow import pipeline_for, pipeline_stage, eligible, stage


@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False,ALLOWED_HOSTS=['testserver'])
class PipelineSplitTests(TestCase):
    setUpTestData=classmethod(fixtures.EventWorkflowTests.setUpTestData.__func__)
    post=fixtures.EventWorkflowTests.post

    def setUp(self):
        fixtures.EventWorkflowTests.setUp(self)

    def intake(self,kind='quoted'):
        self.client.force_login(self.pm)
        r=self.post(self.collection,dict(property=str(self.home.pk),title='Pipeline repair',description='Sample repair',category='Plumbing',job_type=kind,**({'limit':'1000'} if kind=='callout' else {})))
        self.assertEqual(r.status_code,201,r.content)
        self.job=MaintenanceRequest.objects.get(pk=r.json()['id'])
        return self.job

    def act(self,decision,user=None,key=None):
        self.job.refresh_from_db();self.client.force_login(user or self.ops)
        return self.post(reverse('workflow_action',args=[self.job.pk,'jobs-intake']),dict(version=self.job.version,decision=decision),key)

    def approve(self):
        self.client.force_login(self.ops)
        q=self.client.post(reverse('maintenance_quote',args=[self.job.pk]),dict(reference='SPLIT-QUOTE',title='Approved work',scope='Test',amount='1000',attachments=document()),HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(q.status_code,201,q.content);q=q.json()
        sent=self.post(reverse('maintenance_quote_action',args=[self.job.pk,q['id'],'send']),dict(version=q['version']))
        self.assertEqual(sent.status_code,200,sent.content);q=sent.json()
        self.client.force_login(self.pm)
        result=self.post(reverse('maintenance_quote_decision',args=[self.job.pk,q['id']]),dict(version=q['version'],status='approved',reason=''))
        self.assertEqual(result.status_code,200,result.content);self.job.refresh_from_db()

    def rows(self,pipeline,stage='new',user=None):
        self.client.force_login(user or self.ops)
        return self.client.get(reverse('workflow_stages'),{'pipeline':pipeline,'stage':stage})

    def test_quote_approval_moves_to_jobs_new_and_without_deposit_unlocks(self):
        self.intake();self.assertEqual(pipeline_for(self.job),'quotes')
        self.assertEqual(len(self.rows('quotes').json()['results']),1)
        self.assertEqual(self.act('without_deposit').status_code,400)
        self.approve()
        self.assertEqual(len(self.rows('quotes').json()['results']),0)
        self.assertEqual(len(self.rows('jobs').json()['results']),1)
        self.assertFalse(eligible(self.job))
        self.assertEqual(self.act('without_deposit').status_code,200)
        self.job.refresh_from_db();self.assertTrue(eligible(self.job));self.assertEqual(pipeline_stage(self.job,'jobs'),'ready')
        self.assertEqual(len(self.rows('jobs').json()['results']),0)
        self.assertEqual(SchedulingArrangement.objects.count(),1);self.assertEqual(DepositVerification.objects.count(),0)
        self.assertEqual(self.job.invoices.count(),0)

    def test_authorised_callout_enters_jobs_new_and_terms_are_staff_only_once(self):
        self.intake('callout');self.assertEqual(pipeline_for(self.job),'jobs');self.assertEqual(pipeline_stage(self.job,'jobs'),'new');self.assertFalse(eligible(self.job))
        self.assertEqual(self.act('deposit',user=self.pm).status_code,403)
        self.assertIn(self.act('deposit',user=self.tenant).status_code,(403,404))
        self.assertEqual(self.act('invalid').status_code,400)
        self.assertEqual(self.act('deposit').status_code,200)
        self.job.refresh_from_db();self.assertEqual(pipeline_stage(self.job,'jobs'),'deposit_invoice');self.assertFalse(eligible(self.job))
        self.assertEqual(self.act('without_deposit').status_code,400)
        self.assertEqual(WorkflowDecision.objects.filter(operation='jobs-intake').count(),1)
        self.assertEqual(self.rows('jobs',user=self.pm).status_code,403)
        self.client.force_login(self.pm)
        self.assertEqual(len(self.client.get(reverse('workflow_stages')).json()['stages']),8)

    def test_callout_deposit_requires_recorded_verified_half_of_authorisation(self):
        self.intake('callout');self.assertEqual(self.act('deposit').status_code,200)
        self.client.force_login(self.ops)
        r=self.client.post(reverse('maintenance_invoice',args=[self.job.pk]),dict(number='CALL-DEP',purpose='deposit',visibility='shared',amount='500',due_date=str(timezone.localdate()),attachments=document()),HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(r.status_code,201,r.content);invoice=r.json()
        self.job.refresh_from_db();self.assertEqual(stage(self.job),'deposit')
        self.client.force_login(self.pm)
        r=self.post(reverse('maintenance_invoice_report_paid',args=[self.job.pk,invoice['id']]),dict(version=invoice['version']))
        self.assertEqual(r.status_code,201,r.content);self.job.refresh_from_db();self.assertEqual(stage(self.job),'deposit_confirmation');self.assertFalse(eligible(self.job))
        self.client.force_login(self.ops)
        r=self.post(reverse('maintenance_invoice_verify',args=[self.job.pk,invoice['id']]),dict(version=invoice['version']))
        self.assertEqual(r.status_code,201,r.content);self.job.refresh_from_db();self.assertTrue(eligible(self.job));self.assertEqual(stage(self.job),'ready')
        self.assertEqual(DepositVerification.objects.get().amount,Decimal('500'))

    def test_no_deposit_cannot_create_a_deposit_invoice_and_legacy_is_preserved(self):
        self.intake('callout');self.assertEqual(self.act('without_deposit').status_code,200)
        self.client.force_login(self.ops)
        r=self.client.post(reverse('maintenance_invoice',args=[self.job.pk]),dict(number='NO-DEP',purpose='deposit',visibility='shared',amount='500',due_date=str(timezone.localdate()),attachments=document()),HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(r.status_code,400)
        self.job.refresh_from_db();self.job.jobs_payment_route='legacy';self.job.save(update_fields=['jobs_payment_route'])
        self.assertTrue(eligible(self.job))

    def test_tenant_request_waits_for_pm_before_entering_either_pipeline(self):
        self.client.force_login(self.tenant)
        result=self.post(self.collection,dict(property=str(self.home.pk),title='Tenant repair',description='PM review first',category='Plumbing'))
        self.assertEqual(result.status_code,201)
        self.assertEqual(self.rows('quotes').json()['results'],[])
        self.assertEqual(self.rows('jobs').json()['results'],[])

    def test_route_decision_is_idempotent_and_stale_change_is_rejected(self):
        self.intake('callout');key=uuid.uuid4();version=self.job.version
        result=self.act('deposit',key=key);self.assertEqual(result.status_code,200)
        self.client.force_login(self.ops)
        same=self.post(reverse('workflow_action',args=[self.job.pk,'jobs-intake']),dict(version=version,decision='deposit'),key)
        self.assertEqual(same.status_code,200)
        stale=self.post(reverse('workflow_action',args=[self.job.pk,'jobs-intake']),dict(version=version,decision='without_deposit'))
        self.assertEqual(stale.status_code,409)
        self.assertEqual(WorkflowDecision.objects.filter(operation='jobs-intake').count(),1)

    def test_backfill_only_changes_unstarted_uninvoiced_records(self):
        from django.apps import apps
        import importlib
        self.intake('callout');fresh=self.job
        MaintenanceRequest.objects.filter(pk=fresh.pk).update(jobs_payment_route='legacy')
        old=MaintenanceRequest.objects.create(property=self.home,reported_by=self.pm,workflow_version=1,job_type='callout',status='scheduled')
        importlib.import_module('portal.migrations.0037_jobs_payment_route').pending_unstarted(apps,None)
        fresh.refresh_from_db();old.refresh_from_db()
        self.assertEqual(fresh.jobs_payment_route,'pending')
        self.assertEqual(old.jobs_payment_route,'legacy')

    def test_first_approval_after_legacy_intake_still_needs_new_job_decision(self):
        self.intake();self.job.jobs_payment_route='legacy';self.job.save(update_fields=['jobs_payment_route'])
        self.approve()
        self.assertEqual(self.job.jobs_payment_route,'pending')
        self.assertEqual(pipeline_stage(self.job,'jobs'),'new')
