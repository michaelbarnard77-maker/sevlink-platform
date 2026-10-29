import uuid
from unittest.mock import patch
from django.test import TestCase,override_settings
from django.urls import reverse
from . import test_notifications as fixtures, test_manual_documents as docs
from .test_attachments import photo,document
from .models import MaintenanceRequest,MaintenanceAttachment,WorkflowDecision,JobQuotation,UserJobNotification

@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False)
class QuotePhotoTests(TestCase):
    setUpTestData=classmethod(fixtures.EventWorkflowTests.setUpTestData.__func__)
    post=fixtures.EventWorkflowTests.post
    setUp=docs.ManualDocumentTests.setUp
    new_job=fixtures.EventWorkflowTests.new_job
    quote=docs.ManualDocumentTests.quote
    sent=docs.ManualDocumentTests.sent

    def submit(self,user,files):
        self.client.force_login(user)
        response=self.client.post(reverse('maintenance_collection'),dict(property=str(self.home.pk),title='Photo repair',description='Synthetic',category='Plumbing',attachments=files),HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(response.status_code,201,response.content)
        return response.json()

    def review(self,job,files,key=None):
        self.client.force_login(self.pm)
        return self.client.post(reverse('workflow_action',args=[job['id'],'review']),dict(version=str(job['version']),job_type='quoted',urgency='normal',access_responsibility='pm',attachments=files),HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))

    def test_tenant_photos_are_forwarded_without_copy_and_pm_can_add_multiple(self):
        job=self.submit(self.tenant,[photo('tenant-a.png'),photo('tenant-b.png')])
        ids=set(MaintenanceAttachment.objects.filter(request_id=job['id']).values_list('pk',flat=True))
        key=uuid.uuid4();result=self.review(job,[photo('pm-a.png'),photo('pm-b.png')],key)
        self.assertEqual(result.status_code,200,result.content)
        self.assertEqual(self.review(job,[photo('pm-a.png'),photo('pm-b.png')],key).status_code,200)
        self.assertEqual(MaintenanceAttachment.objects.filter(request_id=job['id']).count(),4)
        self.assertTrue(ids.issubset(set(MaintenanceAttachment.objects.filter(request_id=job['id']).values_list('pk',flat=True))))
        self.client.force_login(self.ops)
        detail=self.client.get(reverse('maintenance_detail',args=[job['id']])).json()
        self.assertEqual(len(detail['attachments']),4)
        self.assertTrue(UserJobNotification.objects.filter(user=self.ops,event__request_id=job['id']).exists())

    def test_pm_can_supply_photos_when_tenant_supplied_none_and_upload_directly(self):
        job=self.submit(self.tenant,[])
        self.assertEqual(self.review(job,[photo('a.png'),photo('b.png')]).status_code,200)
        direct=self.submit(self.pm,[photo('pm-direct-a.png'),photo('pm-direct-b.png')])
        self.assertEqual(len(direct['attachments']),2)
        self.assertEqual(direct['status'],'reviewed')

    def test_total_budget_is_server_enforced_atomically_and_per_photo_limit_stays(self):
        job=self.submit(self.tenant,[photo('first.png')]);item=MaintenanceAttachment.objects.get(request_id=job['id'])
        with patch('portal.attachments.PHOTO_TOTAL_BYTES',item.size):
            self.assertEqual(self.review(job,[photo('more.png')]).status_code,400)
        self.assertEqual(MaintenanceAttachment.objects.filter(request_id=job['id']).count(),1)
        self.assertEqual(MaintenanceRequest.objects.get(pk=job['id']).status,'awaiting_review')
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.force_login(self.pm)
        self.assertEqual(self.review(job,[SimpleUploadedFile('large.png',b'x'*(5*1024*1024+1),'image/png')]).status_code,400)

    def test_revision_requires_pm_request_and_upload_can_notify_in_one_step(self):
        self.client.force_login(self.ops);quote=self.sent()
        duplicate=self.client.post(reverse('maintenance_quote_upload',args=[self.job.pk]),dict(reference='QUO-SECOND',amount='1200',attachments=document()),HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(duplicate.status_code,409)
        url=reverse('maintenance_quote_action',args=[self.job.pk,quote['id'],'revise-and-send'])
        retry_key=uuid.uuid4()
        def upload():return self.client.post(url,dict(version=str(quote['version']),reference=quote['reference'],title='Updated scope',amount='1200',attachments=document()),HTTP_IDEMPOTENCY_KEY=str(retry_key))
        self.assertEqual(upload().status_code,409)
        self.client.force_login(self.pm)
        decision=self.post(reverse('maintenance_quote_decision',args=[self.job.pk,quote['id']]),dict(version=quote['version'],status='revision_requested',reason='Please revise scope'))
        self.assertEqual(decision.status_code,200,decision.content);quote=decision.json()
        self.client.force_login(self.ops);result=upload()
        self.assertEqual(result.status_code,201,result.content)
        self.assertEqual(result.json()['status'],'sent')
        self.assertEqual(upload().status_code,200)
        self.assertEqual(JobQuotation.objects.get(pk=quote['id']).status,'superseded')
        self.assertTrue(UserJobNotification.objects.filter(user=self.pm,event__kind='quote_sent',event__details__quote_id=result.json()['id']).exists())

    def test_pm_photo_storage_failure_does_not_forward_or_change_tenant_photos(self):
        job=self.submit(self.tenant,[photo('tenant.png')])
        original=set(MaintenanceAttachment.objects.filter(request_id=job['id']).values_list('pk',flat=True))
        with patch('portal.attachments.storage') as store:
            store.return_value.save.side_effect=OSError('Synthetic storage failure')
            result=self.review(job,[photo('pm.png')])
        self.assertEqual(result.status_code,503,result.content)
        self.assertEqual(MaintenanceRequest.objects.get(pk=job['id']).status,'awaiting_review')
        self.assertEqual(set(MaintenanceAttachment.objects.filter(request_id=job['id']).values_list('pk',flat=True)),original)
        self.assertFalse(WorkflowDecision.objects.filter(request_id=job['id']).exists())

    def test_rejected_quote_enters_declined_pot(self):
        from .workflow import stage,STAGES
        self.client.force_login(self.ops);quote=self.sent()
        self.client.force_login(self.pm)
        result=self.post(reverse('maintenance_quote_decision',args=[self.job.pk,quote['id']]),dict(version=quote['version'],status='rejected',reason='Not proceeding with this quote'))
        self.assertEqual(result.status_code,200,result.content)
        self.job.refresh_from_db()
        self.assertEqual(stage(self.job),'declined')
        self.assertEqual(dict(STAGES)['declined'],'Declined')

    def test_tenant_access_responsibility_is_private(self):
        from .workflow import data
        self.assertNotIn('access_responsibility',data(self.job,self.tenant))
        self.assertIn('access_responsibility',data(self.job,self.pm))
        self.assertIn('access_responsibility',data(self.job,self.ops))
        self.client.force_login(self.tenant)
        response=self.client.get('/')
        if response.status_code==200:
            self.assertNotContains(response,'Sevlink arranges access')
            self.assertNotContains(response,'Agency arranges access')

    def test_forwarded_request_waits_for_operations_assessment(self):
        from .workflow import stage
        for reporter in (self.tenant,self.pm):
            job=self.submit(reporter,[])
            if reporter==self.tenant:
                result=self.review(job,[])
                self.assertEqual(result.status_code,200,result.content)
                job=self.client.get(reverse('maintenance_detail',args=[job['id']])).json()
            saved=MaintenanceRequest.objects.get(pk=job['id'])
            self.assertEqual(stage(saved),'new')
            self.client.force_login(self.pm)
            denied=self.post(reverse('workflow_action',args=[saved.pk,'operations-triage']),dict(version=saved.version,decision='desktop'))
            self.assertEqual(denied.status_code,403)
            self.client.force_login(self.ops)
            key=uuid.uuid4()
            values=dict(version=saved.version,decision='desktop')
            response=self.post(reverse('workflow_action',args=[saved.pk,'operations-triage']),values)
            self.assertEqual(response.status_code,200,response.content)
            saved.refresh_from_db();self.assertEqual(stage(saved),'quoting')
