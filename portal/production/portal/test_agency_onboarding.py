import re
from django.test import TestCase, override_settings, Client
from django.urls import reverse
from .models import User, Agency, Membership, Invitation, MailQueue, Audit

@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False,ALLOWED_HOSTS=['testserver'],SITE_URL='https://portal.example.test',PRIVILEGED_MFA_REQUIRED=False)
class AgencyOnboardingTests(TestCase):
    def setUp(self):
        self.owner=User.objects.create_superuser(username='owner@example.test',email='owner@example.test',password='Owner-pass-987!')
        self.client.force_login(self.owner)
        self.url=reverse('agency_new')
        self.data=dict(agency_name='Test Properties',phone='0810000000',area='Gauteng',admin_name='Agency Owner',admin_email='AGENCY@example.test')

    def test_owner_creates_agency_with_inactive_regular_admin_and_queued_invitation(self):
        self.assertContains(self.client.get(self.url),'Add agency')
        result=self.client.post(self.url,self.data)
        agency=Agency.objects.get();user=User.objects.get(email='agency@example.test')
        self.assertRedirects(result,reverse('agency_accounts',args=[agency.pk]))
        self.assertEqual(agency.kind,'agency');self.assertEqual(user.membership.role,Membership.ADMIN)
        self.assertFalse(user.is_active);self.assertFalse(user.is_staff);self.assertFalse(user.is_superuser);self.assertFalse(user.has_usable_password())
        self.assertEqual(Invitation.objects.get().invited_by,self.owner)
        self.assertEqual(MailQueue.objects.get().recipient,user.email)
        self.assertTrue(Audit.objects.filter(agency=agency,actor=self.owner).exists())

    def test_invitee_must_choose_password_before_activation_and_token_cannot_be_reused(self):
        self.client.post(self.url,self.data)
        token=re.search(r'/invitation/([^/]+)/',MailQueue.objects.get().body).group(1)
        client=Client();url=reverse('accept_invitation',args=[token])
        self.assertContains(client.get(url),'new_password1')
        self.assertEqual(client.post(url,{}).status_code,200)
        user=User.objects.get(email='agency@example.test');self.assertFalse(user.is_active)
        password='Private-client-password-249!'
        self.assertEqual(client.post(url,dict(new_password1=password,new_password2=password)).status_code,302)
        user.refresh_from_db();self.assertTrue(user.is_active);self.assertTrue(user.check_password(password))
        self.assertEqual(client.get(url).status_code,410)

    def test_repeat_or_existing_email_does_not_create_duplicate_or_take_over_account(self):
        self.client.post(self.url,self.data)
        self.assertEqual(self.client.post(self.url,self.data).status_code,200)
        self.assertEqual(Agency.objects.count(),1);self.assertEqual(MailQueue.objects.count(),1)
        self.data['agency_name']='Another agency';self.data['admin_email']=self.owner.email
        self.assertContains(self.client.post(self.url,self.data),'already uses this email')
        self.assertEqual(Agency.objects.count(),1);self.owner.refresh_from_db();self.assertTrue(self.owner.is_superuser)

    def test_only_superadmin_can_create_and_csrf_is_required(self):
        self.client.logout();self.assertEqual(self.client.get(self.url).status_code,302)
        user=User.objects.create_user(username='staff',is_staff=True)
        self.client.force_login(user)
        for method in (self.client.get,self.client.post):self.assertEqual(method(self.url,self.data).status_code,403)
        client=Client(enforce_csrf_checks=True);client.force_login(self.owner)
        self.assertEqual(client.post(self.url,self.data).status_code,403)
        self.assertFalse(Agency.objects.exists())

    def test_legacy_admin_verification_preserves_existing_password(self):
        self.client.post(self.url,self.data)
        user=User.objects.get(email='agency@example.test');user.set_password('Existing-private-password-158!');user.save()
        token=re.search(r'/invitation/([^/]+)/',MailQueue.objects.get().body).group(1)
        self.client.logout();self.assertEqual(self.client.post(reverse('accept_invitation',args=[token])).status_code,302)
        user.refresh_from_db();self.assertTrue(user.is_active);self.assertTrue(user.check_password('Existing-private-password-158!'))

    def test_invitation_queue_failure_rolls_back_agency_and_administrator(self):
        from unittest.mock import patch
        with patch('portal.agency_onboarding.queue_invite',side_effect=RuntimeError('Synthetic queue failure')):
            with self.assertRaises(RuntimeError):self.client.post(self.url,self.data)
        self.assertFalse(Agency.objects.exists());self.assertEqual(User.objects.count(),1)
        self.assertFalse(MailQueue.objects.exists())
