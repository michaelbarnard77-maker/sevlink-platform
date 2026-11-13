import json,uuid
from django.test import TestCase,Client,override_settings
from django.contrib.auth.models import Permission
from .models import User,Agency,Membership,WebsiteEnquiry,WebsiteEnquiryReadReceipt

@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False,ALLOWED_HOSTS=['testserver'],PRIVILEGED_MFA_REQUIRED=False)
class EnquiryWorkspaceTests(TestCase):
    def setUp(self):
        self.owner=User.objects.create_superuser(username='maintenance@example.test',email='maintenance@example.test')
        self.client.force_login(self.owner)
        self.base='/api/maintenance/website-enquiries/'

    def enquiry(self,name='Customer'):
        return WebsiteEnquiry.objects.create(submission_key=uuid.uuid4(),fingerprint='test',name=name,phone='0820000000',email='customer@example.test',client_type='Homeowner / private client',area='Example street',service='Painting',details='Please paint the room.')

    def post(self,path,data,client=None):
        return (client or self.client).post(path,json.dumps(data),content_type='application/json')

    def test_unread_count_clears_on_acknowledgement_and_new_arrival_appears(self):
        one=self.enquiry();two=self.enquiry('Second')
        self.assertEqual(self.client.get(self.base+'unread/').json()['unread'],2)
        data=self.client.get(self.base).json()
        self.assertEqual(len(data['unread_ids']),2)
        self.assertEqual(self.client.get(self.base+'unread/').json()['unread'],2)
        response=self.post(self.base+'read/',{'ids':data['unread_ids']})
        self.assertEqual(response.json()['unread'],0)
        one.refresh_from_db();self.assertEqual(one.status,'new')
        self.client.logout();self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.base+'unread/').json()['unread'],0)
        third=self.enquiry('Third')
        self.assertEqual(self.client.get(self.base+'unread/').json()['unread'],1)
        self.post(self.base+'read/',{'ids':data['unread_ids']})
        self.assertEqual(self.client.get(self.base+'unread/').json()['unread'],1)
        self.assertFalse(WebsiteEnquiryReadReceipt.objects.filter(enquiry=third).exists())

    def test_receipts_are_per_user_and_idempotent(self):
        enquiry=self.enquiry()
        for _ in range(2):self.post(self.base+'read/',{'ids':[str(enquiry.pk)]})
        self.assertEqual(WebsiteEnquiryReadReceipt.objects.count(),1)
        scheduler=User.objects.create_user(username='scheduler',is_staff=True)
        scheduler.user_permissions.add(Permission.objects.get(codename='operate_schedule'))
        self.client.force_login(scheduler)
        self.assertEqual(self.client.get(self.base+'unread/').json()['unread'],1)
        self.assertEqual(self.client.get(self.base).status_code,200)

    def test_customer_and_unprivileged_staff_have_no_access_and_reads_need_csrf(self):
        enquiry=self.enquiry();agency=Agency.objects.create(name='Agency')
        for role in ('admin','pm','tenant'):
            user=User.objects.create_user(username=role,email=role+'@example.test')
            Membership.objects.create(user=user,agency=agency,role=role)
            self.client.force_login(user)
            for path in ('','unread/'):
                self.assertEqual(self.client.get(self.base+path).status_code,403)
            self.assertEqual(self.post(self.base+'read/',{'ids':[str(enquiry.pk)]}).status_code,403)
        staff=User.objects.create_user(username='staff',email='staff@example.test',is_staff=True)
        self.client.force_login(staff);self.assertEqual(self.client.get(self.base).status_code,403)
        self.client.logout();self.assertEqual(self.client.get(self.base).status_code,401)
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.owner)
        self.assertEqual(self.post(self.base+'read/',{'ids':[str(enquiry.pk)]},strict).status_code,403)
        self.assertFalse(WebsiteEnquiryReadReceipt.objects.exists())

    def test_follow_up_status_pagination_and_validation(self):
        enquiries=[self.enquiry(str(n)) for n in range(28)]
        self.assertEqual(len(self.client.get(self.base).json()['results']),25)
        self.assertEqual(len(self.client.get(self.base,{'page':2}).json()['results']),3)
        self.assertEqual(self.post(self.base,{'id':str(enquiries[0].pk),'status':'contacted'}).status_code,200)
        enquiries[0].refresh_from_db();self.assertEqual(enquiries[0].status,'contacted')
        self.assertEqual(self.client.get(self.base+'unread/').json()['unread'],28)
        self.assertEqual(self.post(self.base,{'id':str(enquiries[0].pk),'status':'invalid'}).status_code,400)
        self.assertEqual(self.post(self.base+'read/',{'ids':['invalid']}).status_code,400)
        self.assertEqual(self.post(self.base+'read/',{'ids':[str(enquiries[0].pk)]*201}).status_code,400)

    def test_live_revision_changes_for_arrival_and_own_read_receipts(self):
        url='/api/maintenance/live-revision/'
        before=self.client.get(url).json()['revision']
        enquiry=self.enquiry()
        after=self.client.get(url).json()['revision'];self.assertNotEqual(before,after)
        self.post(self.base+'read/',{'ids':[str(enquiry.pk)]})
        self.assertNotEqual(after,self.client.get(url).json()['revision'])
