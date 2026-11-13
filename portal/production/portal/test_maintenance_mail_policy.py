import uuid
from django.test import TestCase,override_settings
from django.utils import timezone
from django.core import mail
from .test_notifications import EventWorkflowTests
from .events import record
from .notifications import deliver
from .models import OperationsNotification,OperationsInboxItem,JobInvoice,MaintenanceAttachment,InvoiceAction

@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False,ALLOWED_HOSTS=['testserver'],OPERATIONS_NOTIFICATION_EMAIL='maintenance@sevlink.co.za',OPERATIONS_EMAIL_DELIVERY_BACKEND='django.core.mail.backends.locmem.EmailBackend',OPERATIONS_LIVE_DELIVERY_ENABLED=False)
class MaintenanceMailPolicyTests(TestCase):
    setUpTestData=classmethod(EventWorkflowTests.setUpTestData.__func__)
    setUp=EventWorkflowTests.setUp
    new_job=EventWorkflowTests.new_job
    post=EventWorkflowTests.post

    def event(self,kind,details,actor=None,prefix='test:'):
        return record(self.job,actor or self.ops,kind,prefix+str(uuid.uuid4()),details)

    def test_progress_stays_in_portal_without_email_and_old_queue_is_suppressed(self):
        self.new_job()
        event=self.event('workflow_event',{'action':'Attendance confirmed','decision_id':'test'})
        self.assertTrue(OperationsInboxItem.objects.filter(event=event).exists())
        self.assertFalse(OperationsNotification.objects.filter(event=event).exists())
        notification=OperationsNotification.objects.create(event=event,recipient='maintenance@sevlink.co.za')
        self.assertEqual(deliver(),0)
        notification.refresh_from_db();self.assertEqual(notification.state,'suppressed');self.assertIsNone(notification.sent_at)
        self.assertFalse(getattr(mail,'outbox',[]))

    def test_forwarded_tenant_request_is_emailed_only_once(self):
        self.new_job()
        self.event('workflow_event',{'action':'Request reviewed and routed','decision_id':'first'},actor=self.pm)
        self.event('workflow_event',{'action':'Request reviewed and routed','decision_id':'second'},actor=self.pm)
        self.assertEqual(OperationsNotification.objects.count(),1)

    def test_direct_agency_request_does_not_get_second_review_email(self):
        self.new_job(as_pm=True)
        self.event('workflow_event',{'action':'Request reviewed and routed','decision_id':'first'},actor=self.pm)
        self.assertEqual(OperationsNotification.objects.count(),1)

    def test_deposit_and_final_paid_reports_require_real_customer_invoice_claim(self):
        self.new_job()
        for purpose in ('deposit','final'):
            document=MaintenanceAttachment.objects.create(request=self.job,uploaded_by=self.ops,purpose='invoice',storage_key='policy-'+purpose,filename='invoice.pdf',content_type='application/pdf',size=10,sha256='a'*64)
            invoice=JobInvoice.objects.create(request=self.job,document=document,uploaded_by=self.ops,number='TEST-'+purpose,amount=100,due_date=timezone.localdate(),creation_key=uuid.uuid4(),purpose=purpose,visibility='shared')
            claim=InvoiceAction.objects.create(invoice=invoice,actor=self.pm,kind='payment_reported',key=uuid.uuid4(),fingerprint='test')
            self.event('workflow_event',{'action':'Payment reported — verify bank receipt','decision_id':str(claim.pk)},actor=self.pm,prefix='payment-reported:')
        self.assertEqual(OperationsNotification.objects.count(),2)
        self.assertEqual(deliver(),2)
        self.event('workflow_event',{'action':'Payment reported — verify bank receipt','decision_id':'999999999'},actor=self.pm,prefix='payment-reported:')
        self.assertEqual(OperationsNotification.objects.count(),2)

    def test_quote_approval_and_customer_comments_are_emailed_not_rejection_or_staff_updates(self):
        self.new_job()
        for decision in ('approved','rejected'):
            self.event('quote_'+decision,{'quote_id':str(uuid.uuid4()),'amount':'100','status':decision,'reason':''},actor=self.pm)
        for user in (self.pm,self.tenant,self.ops):
            self.event('comment_added',{'comment_id':str(uuid.uuid4()),'text':'Job comment'},actor=user)
        self.event('job_completed',{'status':'completed'})
        self.assertEqual(OperationsNotification.objects.count(),3)

    def test_private_client_comments_are_included_and_internal_notes_are_not(self):
        from types import SimpleNamespace
        from .maintenance_mail_policy import maintenance_email_allowed
        self.assertTrue(maintenance_email_allowed(SimpleNamespace(kind='comment_added',actor_role='client',visibility='shared')))
        self.assertFalse(maintenance_email_allowed(SimpleNamespace(kind='internal_note',actor_role='superadmin',visibility='internal')))
