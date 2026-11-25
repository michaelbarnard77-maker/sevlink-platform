"""Regression boundaries for the redesign entry points and new partner-interest lead."""
from io import StringIO
from django.core import signing
from django.core.management import call_command,CommandError
from django.test import TestCase,Client,override_settings
from .models import User,Agency,Membership,Property,MaintenanceRequest,WebsiteEnquiry,MailQueue,Subcontractor

@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False,PRIVILEGED_MFA_REQUIRED=False,ALLOWED_HOSTS=['testserver'])
class CorporateRedesignTests(TestCase):
    def test_real_shell_loads_corporate_assets_without_demo_javascript(self):
        user=User.objects.create_user(username='preview@example.test',email='preview@example.test')
        agency=Agency.objects.create(name='Test',phone='Test',area='Test')
        Membership.objects.create(user=user,agency=agency,role='pm');self.client.force_login(user)
        result=self.client.get('/maintenance/')
        for name in ('corporate.css','corporate-ui.js','repair-wizard.js','maintenance.js','workflow-ui.js'):
            self.assertContains(result,'/static/'+name)
        self.assertNotContains(result,'src="app.js"')
        self.assertNotContains(result,'id="role"')
        self.assertEqual(MaintenanceRequest.objects.count(),0)

    def test_preview_fixture_refuses_the_normal_database_before_writes(self):
        with self.assertRaisesMessage(CommandError,'only runs with config.redesign_preview'):
            call_command('create_redesign_preview',stdout=StringIO())
        self.assertEqual(User.objects.count(),0)
        self.assertEqual(Agency.objects.count(),0)

    def partner_data(self):
        response=self.client.get('/subcontractors/apply/')
        return dict(business='Example Trade',name='Test Partner',phone='0821234567',email='partner@example.test',trade='Plumbing',area='Pretoria',details='Experienced in repairs. Weekday availability.',consent='on',submission_token=response.context['form']['submission_token'].value())

    def test_partner_lead_is_idempotent_and_never_creates_supplier_or_account(self):
        data=self.partner_data();first=self.client.post('/subcontractors/apply/',data)
        self.assertEqual(first.status_code,302)
        self.assertEqual(WebsiteEnquiry.objects.get().service,'Subcontractor application')
        self.assertEqual(self.client.post('/subcontractors/apply/',data).status_code,302)
        self.assertEqual(WebsiteEnquiry.objects.count(),1)
        self.assertEqual(MailQueue.objects.count(),2)
        self.assertEqual(Subcontractor.objects.count(),0);self.assertEqual(User.objects.count(),0)
        data['business']='Changed business'
        self.assertEqual(self.client.post('/subcontractors/apply/',data).status_code,409)
        self.assertEqual(WebsiteEnquiry.objects.count(),1)

    def test_partner_invalid_nonce_trade_and_csrf_are_rejected(self):
        data=self.partner_data();data['submission_token']='invalid'
        self.assertEqual(self.client.post('/subcontractors/apply/',data).status_code,400)
        data=self.partner_data();data['trade']='forged'
        self.assertEqual(self.client.post('/subcontractors/apply/',data).status_code,400)
        self.assertEqual(Client(enforce_csrf_checks=True).post('/subcontractors/apply/',data).status_code,403)
        self.assertEqual(WebsiteEnquiry.objects.count(),0)
        self.assertEqual(MailQueue.objects.count(),0)
