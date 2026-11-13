import uuid
from unittest.mock import patch
from django.core import signing
from django.test import TestCase,Client,override_settings
from .agency_enquiries import SALT
from .models import WebsiteEnquiry,MailQueue,User,Agency,Invitation
from .website_enquiries import email_bodies

@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False,ALLOWED_HOSTS=['testserver'])
class AgencyEnquiryTests(TestCase):
    def payload(self):
        return dict(agency='Example Properties',first='Alex',last='Morgan',phone='0821234567',email='AGENCY@example.test',interest='demo',timeframe='three_months',consent='on',submission_token=signing.dumps(str(uuid.uuid4()),salt=SALT))

    def test_public_form_available_with_registration_disabled(self):
        with override_settings(AGENCY_REGISTRATION_ENABLED=False):result=self.client.get('/register/')
        self.assertContains(result,'Submit request');self.assertContains(result,'Within the next 3 months')
        self.assertContains(result,'I’d like a demonstration of the portal');self.assertNotContains(result,'password1')

    def test_submission_queues_lead_and_confirmation_without_creating_accounts(self):
        data=self.payload();result=self.client.post('/register/',data)
        self.assertEqual(result.status_code,302)
        enquiry=WebsiteEnquiry.objects.get()
        self.assertEqual(enquiry.name,'Alex Morgan');self.assertEqual(enquiry.email,'agency@example.test')
        self.assertIn('Example Properties',enquiry.details);self.assertIn('Within the next 3 months',enquiry.details)
        self.assertEqual(set(MailQueue.objects.values_list('recipient',flat=True)),{'maintenance@sevlink.co.za','agency@example.test'})
        self.assertContains(self.client.get(result.url),enquiry.reference)
        self.assertEqual(self.client.post('/register/',data).status_code,302);self.assertEqual(MailQueue.objects.count(),2)
        for model in (Agency,User,Invitation):self.assertFalse(model.objects.exists())
        data['agency']='Changed agency';self.assertEqual(self.client.post('/register/',data).status_code,409)

    def test_invalid_and_spam_submissions_are_not_saved(self):
        for change in [{'phone':'invalid'},{'email':'invalid'},{'consent':''},{'interest':'other'},{'timeframe':'next_year'},{'website':'spam'},{'submission_token':'invalid'}]:
            data=self.payload();data.update(change);self.assertEqual(self.client.post('/register/',data).status_code,400)
        with patch('portal.agency_enquiries.limited',return_value=True):self.assertEqual(self.client.post('/register/',self.payload()).status_code,429)
        self.assertFalse(WebsiteEnquiry.objects.exists());self.assertFalse(MailQueue.objects.exists())

    def test_csrf_required_and_request_fields_are_escaped_in_email(self):
        strict=Client(enforce_csrf_checks=True)
        self.assertEqual(strict.post('/register/',self.payload()).status_code,403)
        data=self.payload();data['agency']='<script>bad()</script>';self.client.post('/register/',data)
        enquiry=WebsiteEnquiry.objects.get();plain,html=email_bodies(enquiry,enquiry.email)
        self.assertIn('agency request',plain);self.assertIn('Agency consultation',html)
        self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html);self.assertNotIn('Work requested',html)

    def test_queue_failure_rolls_back_saved_lead(self):
        with patch('portal.agency_enquiries.MailQueue.objects.create',side_effect=RuntimeError('test')):
            with self.assertRaises(RuntimeError):self.client.post('/register/',self.payload())
        self.assertFalse(WebsiteEnquiry.objects.exists())

    def test_account_worker_uses_agency_email_and_reply_to_in_local_preview(self):
        from django.core import mail
        from .account_mail import deliver
        self.client.post('/register/',self.payload())
        item=MailQueue.objects.get(recipient='maintenance@sevlink.co.za')
        provider=mail.get_connection('django.core.mail.backends.locmem.EmailBackend')
        with patch('portal.account_mail.get_connection',return_value=provider):
            self.assertEqual(deliver(limit=1,preview=True,message_id=item.pk),0)
        self.assertEqual(mail.outbox[0].reply_to,['agency@example.test'])
        self.assertIn('Agency consultation',mail.outbox[0].alternatives[0][0])
        self.assertNotIn('Work requested',mail.outbox[0].alternatives[0][0])
        item.refresh_from_db();self.assertIsNone(item.sent_at)
