from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.utils import timezone
from .models import User, Agency, Membership, Property, Tenancy, Invitation, AccountLifecycleEvent, MaintenanceRequest
from .services import queue_invite

@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class LifecycleTests(TestCase):
    def setUp(self):
        self.a = Agency.objects.create(name='Agency A')
        self.b = Agency.objects.create(name='Agency B')
        self.admin = self.user('owner', Membership.ADMIN)
        self.pm = self.user('manager', Membership.PM)
        self.tenant = self.user('tenant', Membership.TENANT)
        self.prop = Property.objects.create(agency=self.a, manager=self.pm, name='Home', address='Test')
        self.tenancy = Tenancy.objects.create(property=self.prop, user=self.tenant, email=self.tenant.email)
        self.job = MaintenanceRequest.objects.create(property=self.prop, reported_by=self.tenant, title='Tap', description='Leak', category='Plumbing')
        self.client.force_login(self.admin)

    def user(self, name, role, agency=None):
        u = User.objects.create_user(username=name+'@example.test', email=name+'@example.test', password='Long-testing-passphrase-482!')
        Membership.objects.create(user=u, agency=agency or self.a, role=role)
        return u

    def action(self, kind, pk, **kw):
        return self.client.post(f'/accounts/{self.a.pk}/{kind}/{pk}/', {'confirm':'on','reason':'Verified test instruction', **kw})

    def test_deactivation_preserves_history_and_revokes_existing_session(self):
        from django.test import Client
        tenant_client = Client(); tenant_client.force_login(self.tenant)
        self.assertEqual(self.action('deactivate', self.tenant.pk).status_code,302)
        self.assertEqual(tenant_client.get(f'/api/maintenance/requests/{self.job.pk}/').status_code,401)
        self.tenancy.refresh_from_db(); self.assertFalse(self.tenancy.active)
        self.assertTrue(MaintenanceRequest.objects.filter(pk=self.job.pk).exists())
        self.assertEqual(AccountLifecycleEvent.objects.get().action,'deactivate')
        self.assertEqual(self.action('reactivate', self.tenant.pk).status_code,302)
        self.tenancy.refresh_from_db(); self.assertFalse(self.tenancy.active)
        self.assertEqual(tenant_client.get('/api/maintenance/context/').status_code,401)

    def test_move_out_revokes_property_access_without_disabling_other_tenancy(self):
        second = Property.objects.create(agency=self.a, name='Other', address='Other')
        Tenancy.objects.create(property=second, user=self.tenant, email=self.tenant.email)
        self.assertEqual(self.action('move-out', self.tenancy.pk).status_code,302)
        self.client.force_login(self.tenant)
        self.assertEqual(self.client.get(f'/api/maintenance/requests/{self.job.pk}/').status_code,404)
        self.assertContains(self.client.get('/'), 'Other')

    def test_confirmation_permissions_and_foreign_targets(self):
        self.assertEqual(self.action('deactivate',self.pm.pk,confirm='').status_code,200)
        self.pm.refresh_from_db(); self.assertTrue(self.pm.is_active)
        self.assertEqual(self.action('deactivate',self.admin.pk).status_code,403)
        foreign = self.user('foreign',Membership.TENANT,self.b)
        self.assertEqual(self.action('deactivate',foreign.pk).status_code,404)
        self.client.force_login(self.pm)
        self.assertEqual(self.action('move-out',self.tenancy.pk).status_code,403)
        self.assertEqual(AccountLifecycleEvent.objects.count(),0)

    def test_cancel_invitation_prevents_acceptance(self):
        invitation = queue_invite(agency=self.a, email='new@example.test',name='New',role='pm',actor=self.admin)
        self.assertEqual(self.action('cancel-invitation',invitation.pk).status_code,302)
        invitation.refresh_from_db(); self.assertIsNotNone(invitation.revoked_at)

    def test_existing_tenant_must_authenticate_and_accept_without_password_reset(self):
        self.assertEqual(self.client.post(f'/properties/{self.prop.pk}/tenant/',{
            'name':'Existing','email':self.tenant.email}).status_code,302)
        invitation = Invitation.objects.get(email=self.tenant.email)
        from .models import MailQueue
        import re
        token = re.search(r'/invitation/([^/]+)/',MailQueue.objects.latest('pk').body).group(1)
        self.client.logout()
        url = '/invitation/'+token+'/'
        self.assertEqual(self.client.post(url).status_code,302)
        invitation.refresh_from_db(); self.assertIsNone(invitation.accepted_at)
        self.client.force_login(self.pm)
        self.assertEqual(self.client.post(url).status_code,403)
        self.client.force_login(self.tenant)
        self.assertEqual(self.client.post(url,{'new_password1':'attacker'}).status_code,302)
        self.tenant.refresh_from_db(); self.assertTrue(self.tenant.check_password('Long-testing-passphrase-482!'))
        self.assertEqual(self.client.post(url).status_code,410)

    def test_pm_deactivation_clears_allocations(self):
        self.assertEqual(self.action('deactivate', self.pm.pk).status_code,302)
        self.prop.refresh_from_db(); self.assertIsNone(self.prop.manager_id)

    def test_delegated_staff_login_lands_in_authorised_workspace(self):
        staff = User.objects.create_user(username='staff@example.test',email='staff@example.test',password='Long-testing-passphrase-482!',is_staff=True)
        staff.user_permissions.add(Permission.objects.get(codename='operate_schedule'))
        self.client.logout()
        response=self.client.post('/login/',{'username':staff.email,'password':'Long-testing-passphrase-482!'},follow=True)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.redirect_chain[-1][0],'/maintenance/')

    def test_production_admission_gate_creates_no_unapproved_agency(self):
        self.client.logout()
        with override_settings(AGENCY_REGISTRATION_ENABLED=False):
            self.assertEqual(self.client.get('/register/').status_code,403)
        with override_settings(AGENCY_REGISTRATION_ENABLED=True,AGENCY_REGISTRATION_ALLOWED_EMAILS=['approved@example.test']):
            response=self.client.post('/register/',{'agency_name':'Unapproved','first_name':'Unapproved','email':'unapproved@example.test','phone':'test','area':'Test','password1':'Long-testing-passphrase-482!','password2':'Long-testing-passphrase-482!'})
            self.assertEqual(response.status_code,200)
            self.assertFalse(Agency.objects.filter(name='Unapproved').exists())
            self.assertFalse(User.objects.filter(email='unapproved@example.test').exists())
