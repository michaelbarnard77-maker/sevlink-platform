import json
import uuid
from django.test import TestCase,Client,override_settings
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from . import test_notifications as fixtures
from .models import (MaintenanceRequest,JobInternalNoteRevision,WorkflowDecision,User,Membership,Audit,MailQueue,OperationsNotification,JobActivity)

@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False,ALLOWED_HOSTS=['testserver'],PRIVILEGED_MFA_REQUIRED=False)
class InternalJobNotesTests(TestCase):
    setUpTestData=classmethod(fixtures.EventWorkflowTests.setUpTestData.__func__)

    def setUp(self):
        self.job=MaintenanceRequest.objects.create(property=self.home,reported_by=self.tenant,title='Repair',description='Shared description',category='Plumbing',status='reviewed',workflow_version=1,job_type='quoted',internal_notes='LEGACY INTERNAL NOTE')
        self.url=reverse('job_internal_note',args=[self.job.pk])
        self.client.force_login(self.ops)

    def save_note(self,text='CONFIDENTIAL INTERNAL HANDOVER',version=0,key=None,client=None):
        return (client or self.client).post(self.url,json.dumps(dict(text=text,version=version)),content_type='application/json',HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))

    def test_edit_history_is_private_audited_and_leaves_workflow_and_email_unchanged(self):
        from .workflow import stage
        WorkflowDecision.objects.create(request=self.job,actor=self.ops,operation='manual-stage',key=uuid.uuid4(),fingerprint='test',snapshot={'stage':'booked','version':self.job.version})
        before=stage(self.job);job_version=self.job.version
        result=self.save_note();self.assertEqual(result.status_code,200,result.content)
        self.assertEqual(result.json()['version'],1);self.assertEqual(result.json()['history_count'],1)
        self.assertEqual(self.save_note('Updated internal position',1).status_code,200)
        history=self.client.get(self.url,{'history':'1'}).json()
        self.assertEqual([r['text'] for r in history['history']],['CONFIDENTIAL INTERNAL HANDOVER','LEGACY INTERNAL NOTE'])
        self.job.refresh_from_db();self.assertEqual(self.job.version,job_version);self.assertEqual(self.job.status,'reviewed');self.assertEqual(stage(self.job),before)
        self.assertEqual(Audit.objects.filter(action='Job internal note saved').count(),2)
        for model in (MailQueue,OperationsNotification,JobActivity):self.assertFalse(model.objects.exists())
        revision=JobInternalNoteRevision.objects.first()
        revision.text='overwrite'
        with self.assertRaises(ValidationError):revision.save()
        with self.assertRaises(ValidationError):JobInternalNoteRevision.objects.all().delete()

    def test_customer_roles_and_unprivileged_staff_cannot_read_or_write_notes(self):
        regular_staff=User.objects.create_user(username='unprivileged-staff',is_staff=True)
        for user in (self.tenant,self.pm,self.admin,self.foreign,regular_staff):
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.url).status_code,403)
            self.assertEqual(self.save_note().status_code,403)
        self.client.logout();self.assertEqual(self.client.get(self.url).status_code,401)
        self.assertFalse(JobInternalNoteRevision.objects.exists())

    def test_explicit_sevlink_schedule_permission_can_edit_but_agency_membership_does_not_grant_it(self):
        scheduler=User.objects.create_user(username='scheduler',email='scheduler@example.test',is_staff=True)
        scheduler.user_permissions.add(Permission.objects.get(codename='operate_schedule'))
        self.client.force_login(scheduler);self.assertEqual(self.client.get(self.url).status_code,200)
        self.assertEqual(self.save_note().status_code,200)
        Membership.objects.create(user=scheduler,agency=self.agency,role='admin')
        self.assertEqual(self.client.get(self.url).status_code,403)

    def test_stale_edits_and_conflicting_retry_keys_do_not_replace_newer_note(self):
        key=uuid.uuid4();self.assertEqual(self.save_note(key=key).status_code,200)
        self.assertEqual(self.save_note(key=key).status_code,200)
        self.assertEqual(JobInternalNoteRevision.objects.count(),2)
        self.assertEqual(self.save_note('A stale replacement',0).status_code,409)
        self.assertEqual(self.save_note('Another text',0,key=key).status_code,409)
        self.assertEqual(self.save_note('New current position',1).status_code,200)
        self.assertEqual(self.save_note(key=key).json()['text'],'New current position')
        self.job.refresh_from_db();self.assertEqual(self.job.internal_notes,'New current position')

    def test_notes_never_enter_customer_job_payloads_or_update_feed(self):
        self.save_note()
        for user in (self.pm,self.admin,self.tenant):
            self.client.force_login(user)
            for url in [reverse('maintenance_detail',args=[self.job.pk]),reverse('maintenance_collection')]:
                response=self.client.get(url);self.assertEqual(response.status_code,200)
                self.assertNotIn('CONFIDENTIAL INTERNAL HANDOVER',response.content.decode());self.assertNotIn('LEGACY INTERNAL NOTE',response.content.decode())
                self.assertNotIn('can_edit_internal_notes',response.content.decode())
        self.client.force_login(self.ops)
        self.assertTrue(self.client.get(reverse('maintenance_detail',args=[self.job.pk])).json()['can_edit_internal_notes'])

    def test_csrf_validation_length_and_closed_job_notes(self):
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.ops)
        self.assertEqual(self.save_note(client=strict).status_code,403)
        self.assertEqual(self.save_note('x'*6001).status_code,400)
        self.job.status='closed';self.job.closed_at=timezone.now();self.job.save(update_fields=['status','closed_at'])
        self.assertEqual(self.save_note('').status_code,200)
        self.job.refresh_from_db();self.assertEqual(self.job.status,'closed');self.assertEqual(self.job.internal_notes,'')
        self.assertEqual(self.client.get(self.url,{'history':'1','page':'0'}).status_code,400)

    def test_history_is_paginated_and_live_revision_changes(self):
        from .live_updates import revision
        first=self.client.get('/api/maintenance/live-revision/').json()['revision']
        self.save_note()
        second=self.client.get('/api/maintenance/live-revision/').json()['revision']
        self.assertNotEqual(first,second)
        for version in range(1,27):self.save_note('Internal note '+str(version),version)
        page=self.client.get(self.url,{'history':'1'}).json()
        self.assertEqual(len(page['history']),25);self.assertTrue(page['has_next'])
        self.assertEqual(len(self.client.get(self.url,{'history':'1','page':2}).json()['history']),2)
