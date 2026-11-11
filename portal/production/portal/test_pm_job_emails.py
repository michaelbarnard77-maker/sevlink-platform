import uuid
from django.test import TestCase,override_settings
from django.core import mail
from .test_notifications import EventWorkflowTests
from .events import record
from .models import OperationsNotification
from .notifications import deliver

@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False,ALLOWED_HOSTS=['testserver'],OPERATIONS_NOTIFICATION_EMAIL='maintenance@sevlink.co.za',OPERATIONS_EMAIL_DELIVERY_BACKEND='django.core.mail.backends.locmem.EmailBackend',OPERATIONS_LIVE_DELIVERY_ENABLED=False)
class PMJobEmailTests(TestCase):
    setUpTestData=classmethod(EventWorkflowTests.setUpTestData.__func__)
    def setUp(self):
        EventWorkflowTests.setUp(self)
        self.pm.email=self.pm.username;self.pm.save(update_fields=['email'])
    post=EventWorkflowTests.post
    new_job=EventWorkflowTests.new_job

    def event(self,kind,details,actor=None):
        return record(self.job,actor or self.pm,kind,'pm-mail:'+str(uuid.uuid4()),details)

    def test_tenant_request_emails_assigned_pm_only(self):
        self.new_job()
        self.assertEqual(list(OperationsNotification.objects.values_list('recipient',flat=True)),[self.pm.email])
        self.assertEqual(deliver(),1)
        self.assertEqual(mail.outbox[0].to,[self.pm.email])
        self.assertNotIn('PRIVATE ACCESS CODE',mail.outbox[0].body)
        self.assertNotIn('PRIVATE PHONE',mail.outbox[0].body)

    def test_actionable_events_deliver_separately_without_other_pms(self):
        self.new_job(as_pm=True)
        event=self.event('quote_approved',{'quote_id':str(uuid.uuid4()),'amount':'100','status':'approved','reason':''})
        self.assertEqual(set(OperationsNotification.objects.filter(event=event).values_list('recipient',flat=True)),{self.pm.email,'maintenance@sevlink.co.za'})
        self.assertEqual(deliver(),4)
        self.assertEqual(len({m.extra_headers['Message-ID'] for m in mail.outbox}),4)
        self.assertFalse(OperationsNotification.objects.filter(recipient__in=[self.other_pm.email,self.foreign.email,self.tenant.email,self.admin.email]).exists())

    def test_reassigned_pm_does_not_receive_queued_details(self):
        self.new_job()
        self.home.manager=self.other_pm;self.home.save(update_fields=['manager'])
        self.assertEqual(deliver(),0)
        self.assertEqual(OperationsNotification.objects.get().state,'suppressed')

    def test_inactive_and_foreign_pm_excluded(self):
        self.new_job()
        OperationsNotification.objects.all().delete()
        self.pm.is_active=False;self.pm.save(update_fields=['is_active'])
        self.event('quote_approved',{'quote_id':str(uuid.uuid4()),'amount':'100','status':'approved','reason':''})
        self.assertEqual(list(OperationsNotification.objects.values_list('recipient',flat=True)),['maintenance@sevlink.co.za'])
        self.home.manager=self.foreign;self.home.save(update_fields=['manager'])
        self.job.property=self.home
        event=self.event('quote_approved',{'quote_id':str(uuid.uuid4()),'amount':'100','status':'approved','reason':''})
        self.assertEqual(list(OperationsNotification.objects.filter(event=event).values_list('recipient',flat=True)),['maintenance@sevlink.co.za'])

    def test_internal_notes_and_progress_not_copied(self):
        self.new_job();OperationsNotification.objects.all().delete()
        self.event('internal_note',{'comment_id':str(uuid.uuid4()),'text':'Private supplier costs'},actor=self.ops)
        self.event('workflow_event',{'action':'Attendance confirmed','decision_id':'test'},actor=self.ops)
        self.assertFalse(OperationsNotification.objects.exists())

    def test_feedback_identifies_individual_recipient_without_affecting_other_delivery(self):
        from .email_operations import feedback
        from django.utils import timezone
        self.new_job(as_pm=True)
        pm_notice=OperationsNotification.objects.get(recipient=self.pm.email)
        maintenance=OperationsNotification.objects.exclude(pk=pm_notice.pk).get()
        payload=dict(event_id=str(pm_notice.event_id),provider_event_id=str(uuid.uuid4()),kind='bounce',occurred_at=timezone.now().isoformat())
        with self.assertRaises(ValueError):feedback(payload)
        self.assertTrue(feedback(dict(payload,notification_id=pm_notice.pk)))
        maintenance.refresh_from_db();self.assertEqual(maintenance.feedback_status,'unknown')
        self.assertEqual(deliver(),1)
        self.assertEqual(mail.outbox[0].to,[maintenance.recipient])

    def test_deposit_and_final_payment_reports_are_copied_without_invoice_attachment_or_private_details(self):
        from .models import MaintenanceAttachment,JobInvoice,InvoiceAction
        from django.utils import timezone
        self.new_job();OperationsNotification.objects.all().delete()
        for purpose in ('deposit','final'):
            doc=MaintenanceAttachment.objects.create(request=self.job,uploaded_by=self.ops,purpose='invoice',storage_key='pm-'+purpose,filename='invoice.pdf',content_type='application/pdf',size=10,sha256='a'*64)
            invoice=JobInvoice.objects.create(request=self.job,document=doc,uploaded_by=self.ops,number='PM-'+purpose,amount=100,due_date=timezone.localdate(),creation_key=uuid.uuid4(),purpose=purpose,visibility='shared')
            action=InvoiceAction.objects.create(invoice=invoice,actor=self.pm,kind='payment_reported',key=uuid.uuid4(),fingerprint='test')
            event=record(self.job,self.pm,'workflow_event','payment-reported:'+str(uuid.uuid4()),{'action':'Payment reported — verify bank receipt','decision_id':str(action.pk)},private=True)
            self.assertEqual(set(OperationsNotification.objects.filter(event=event).values_list('recipient',flat=True)),{self.pm.email,'maintenance@sevlink.co.za'})
        self.assertEqual(deliver(),4)
        self.assertTrue(all(not m.attachments for m in mail.outbox))
