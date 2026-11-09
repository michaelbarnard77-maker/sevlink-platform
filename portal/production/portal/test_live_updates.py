import uuid
from django.test import TestCase, override_settings
from .models import User, Agency, Membership, Property, MaintenanceRequest, JobQuotation, AttendanceRequest

@override_settings(SECURE_SSL_REDIRECT=False,PRIVILEGED_MFA_REQUIRED=False,ALLOWED_HOSTS=['testserver'])
class LiveRevisionTests(TestCase):
    def setUp(self):
        self.owner=User.objects.create_superuser(username='owner',email='owner@example.test',password='password')
        self.manager=User.objects.create_user(username='manager',email='manager@example.test',password='password')
        self.agency=Agency.objects.create(name='My agency')
        self.other=Agency.objects.create(name='Other agency')
        Membership.objects.create(user=self.manager,agency=self.agency,role=Membership.PM)
        self.property=Property.objects.create(agency=self.agency,manager=self.manager,name='Home',address='My street')
        self.other_property=Property.objects.create(agency=self.other,name='Private home',address='Other street')
        self.job=MaintenanceRequest.objects.create(property=self.property,reported_by=self.manager,title='Repair',description='Work',category='Painting')
        self.other_job=MaintenanceRequest.objects.create(property=self.other_property,reported_by=self.owner,title='Other repair',description='Private',category='Painting')

    def revision(self):
        response=self.client.get('/api/maintenance/live-revision/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(set(response.json()),{'revision'})
        self.assertIn('no-store',response['Cache-Control'])
        return response.json()['revision']

    def test_login_and_workspace_access_required(self):
        self.assertEqual(self.client.get('/api/maintenance/live-revision/').status_code,401)
        outsider=User.objects.create_user(username='outsider')
        self.client.force_login(outsider)
        self.assertEqual(self.client.get('/api/maintenance/live-revision/').status_code,403)

    def test_scope_is_stable_and_other_agency_cannot_invalidate_it(self):
        self.client.force_login(self.manager)
        before=self.revision()
        self.other_job.version+=1;self.other_job.save()
        self.assertEqual(before,self.revision())
        self.job.version+=1;self.job.save()
        self.assertNotEqual(before,self.revision())
        self.assertEqual(self.revision(),self.revision())

    def test_quote_decision_changes_revision_without_parent_update(self):
        self.client.force_login(self.owner)
        quote=JobQuotation.objects.create(request=self.job,created_by=self.owner,title='Paint',scope='Room',amount=100,status='sent',creation_key=uuid.uuid4())
        before=self.revision()
        quote.status='approved';quote.version+=1;quote.save()
        self.assertNotEqual(before,self.revision())

    def test_attendance_preference_changes_revision(self):
        self.client.force_login(self.owner)
        before=self.revision()
        AttendanceRequest.objects.create(request=self.job,requested_by=self.manager,preference='call',requested_date=None,requested_window='',confirmed_at=None,confirmed_by=None)
        self.assertNotEqual(before,self.revision())

    def test_payments_change_marker_without_parent_job_update(self):
        from .models import JobInvoice, MaintenanceAttachment
        from django.utils import timezone
        self.client.force_login(self.owner)
        document=MaintenanceAttachment.objects.create(request=self.job,uploaded_by=self.owner,purpose='invoice',storage_key='test-invoice',filename='test.pdf',content_type='application/pdf',size=10,sha256='a'*64)
        invoice=JobInvoice.objects.create(request=self.job,document=document,uploaded_by=self.owner,number='TEST-INVOICE',amount=100,due_date=timezone.localdate(),creation_key=uuid.uuid4())
        before=self.revision()
        invoice.payment_status='paid';invoice.paid_amount=100;invoice.version+=1;invoice.save()
        self.assertNotEqual(before,self.revision())

    def test_non_assigned_property_stays_out_of_pm_scope(self):
        another=Property.objects.create(agency=self.agency,name='Other manager home',address='Private street')
        self.client.force_login(self.manager)
        before=self.revision()
        MaintenanceRequest.objects.create(property=another,reported_by=self.owner,title='Hidden repair',description='Private',category='Painting')
        self.assertEqual(before,self.revision())
