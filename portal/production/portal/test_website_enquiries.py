import uuid
from unittest.mock import patch
from django.core import signing
from django.test import TransactionTestCase, Client, override_settings
from .models import WebsiteEnquiry, MailQueue, User
from .website_enquiries import SALT, email_bodies

@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False,ALLOWED_HOSTS=['testserver'],PRIVILEGED_MFA_REQUIRED=False)
class WebsiteEnquiryTests(TransactionTestCase):
    def payload(self):
        return dict(name='Home Owner',phone='0810285034',email='owner@example.test',clientType='Homeowner / private client',area='Cape Town',service='Painting',details='Paint the room.\nTwo walls.',consent='on',submission_token=signing.dumps(str(uuid.uuid4()),salt=SALT))

    def test_submit_saves_and_queues_once_with_reference(self):
        data=self.payload()
        response=self.client.post('/',data)
        self.assertEqual(response.status_code,201)
        enquiry=WebsiteEnquiry.objects.get()
        self.assertEqual(response.json()['reference'],enquiry.reference)
        self.assertEqual(set(MailQueue.objects.values_list('recipient',flat=True)),{'owner@example.test','maintenance@sevlink.co.za'})
        self.assertEqual(self.client.post('/',data).status_code,200)
        self.assertEqual(MailQueue.objects.count(),2)
        data['details']='Changed work'
        self.assertEqual(self.client.post('/',data).status_code,409)
        self.assertFalse(User.objects.exists())

    def test_validation_and_spam_controls_do_not_save_or_send(self):
        for change in [{'email':'invalid'},{'consent':''},{'website':'bot.test'},{'submission_token':'fake'},{'service':'made up'},{'details':'x'*2501}]:
            data=self.payload();data.update(change)
            self.assertEqual(self.client.post('/',data).status_code,400)
        with patch('portal.website_enquiries.limited',return_value=True):
            self.assertEqual(self.client.post('/',self.payload()).status_code,429)
        self.assertFalse(WebsiteEnquiry.objects.exists())
        self.assertFalse(MailQueue.objects.exists())

    def test_csrf_is_required_and_rendered(self):
        client=Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/',self.payload()).status_code,403)
        page=client.get('/')
        self.assertContains(page,'name="csrfmiddlewaretoken"')
        self.assertContains(page,'name="submission_token"')
        data=self.payload();data['csrfmiddlewaretoken']=client.cookies['csrftoken'].value
        self.assertEqual(client.post('/',data).status_code,201)
        self.assertIn('no-store',page['Cache-Control'])

    def test_inbox_requires_authorised_staff_and_status_post(self):
        self.client.post('/',self.payload());enquiry=WebsiteEnquiry.objects.get()
        self.assertEqual(self.client.get('/enquiries/').status_code,302)
        user=User.objects.create_user(username='outsider',email='outsider@example.test',password='secret',is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get('/enquiries/').status_code,403)
        self.assertEqual(self.client.post('/enquiries/',{'id':enquiry.pk,'status':'closed'}).status_code,403)
        user.is_superuser=True;user.save()
        self.assertContains(self.client.get('/enquiries/'),enquiry.reference)
        self.assertEqual(self.client.post('/enquiries/',{'id':enquiry.pk,'status':'contacted'}).status_code,302)
        enquiry.refresh_from_db();self.assertEqual(enquiry.status,'contacted')

    def test_email_has_structured_escaped_content_and_confirmation(self):
        data=self.payload();data['details']='<script>alert(1)</script>\nSecond line'
        self.client.post('/',data);enquiry=WebsiteEnquiry.objects.get()
        plain,html=email_bodies(enquiry,enquiry.email)
        self.assertIn('not a confirmed booking',plain)
        self.assertIn(enquiry.reference,html)
        self.assertIn('Work requested',html)
        self.assertIn('&lt;script&gt;',html)
        self.assertNotIn('<script>',html)
        self.assertIn('<br>Second line',html)
        self.assertNotIn('&lt;br&gt;',html)
        self.assertNotIn('/enquiries/',html)
        self.assertIn('https://portal.sevlink.co.za/enquiries/',email_bodies(enquiry,'maintenance@sevlink.co.za')[1])

    @override_settings(SMTP_DELIVERY_ENABLED=True,EMAIL_HOST='smtp.example.test',EMAIL_HOST_USER='test',EMAIL_HOST_PASSWORD='test',EMAIL_USE_TLS=True,EMAIL_USE_SSL=False)
    def test_worker_delivers_html_and_reply_to_without_changing_other_mail(self):
        from django.core import mail
        from django.core.mail import get_connection
        from .account_mail import deliver
        self.client.post('/',self.payload())
        with patch('portal.account_mail.get_connection',return_value=get_connection('django.core.mail.backends.locmem.EmailBackend')):
            self.assertEqual(deliver(),2)
        self.assertEqual(len(mail.outbox),2)
        staff=next(m for m in mail.outbox if m.to==['maintenance@sevlink.co.za'])
        self.assertEqual(staff.reply_to,['owner@example.test'])
        self.assertEqual(staff.from_email,'Sevlink <maintenance@sevlink.co.za>')
        self.assertIn('Work requested',staff.alternatives[0].content)
        self.assertEqual(WebsiteEnquiry.objects.count(),1)
        self.assertEqual(MailQueue.objects.filter(sent_at__isnull=False).count(),2)
