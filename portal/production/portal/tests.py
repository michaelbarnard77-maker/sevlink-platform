import re
from datetime import timedelta
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from .models import User, Agency, Membership, Property, Tenancy, Invitation, MailQueue, Audit
from .services import digest

@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False,ALLOWED_HOSTS=['testserver'],SITE_URL='https://portal.example.test')
class OnboardingTests(TestCase):
    password = 'Sample-long-password-971!'
    def token(self,email):
        body = MailQueue.objects.filter(recipient=email).latest('pk').body
        return re.search(r'/invitation/([^/]+)/',body).group(1)
    def new_user(self,email,agency,role):
        u = User.objects.create_user(username=email,email=email,password=self.password,first_name=email.split('@')[0])
        Membership.objects.create(user=u,agency=agency,role=role)
        return u
    def register(self,email='owner@example.test'):
        return self.client.post('/register/',{'agency_name':'Oak & River','first_name':'Michael','email':email,'phone':'0810000000','area':'Gauteng','password1':self.password,'password2':self.password})
    def test_register_verify_invite_pm_property_tenant(self):
        self.assertEqual(self.register().status_code,200)
        admin = User.objects.get(email='owner@example.test')
        self.assertFalse(admin.is_active)
        self.assertFalse(admin.check_password('wrong'))
        self.assertTrue(admin.check_password(self.password))
        self.assertFalse(self.client.login(username=admin.username,password=self.password))
        token = self.token(admin.email)
        self.assertFalse(Invitation.objects.filter(token_hash=token).exists())
        self.assertEqual(self.client.post('/invitation/'+token+'/').status_code,302)
        admin.refresh_from_db()
        self.assertTrue(admin.is_active)
        self.assertEqual(self.client.get('/').status_code,302)
        self.client.post('/team/invite/',{'name':'Sarah','email':'sarah@example.test'})
        pm_token = self.token('sarah@example.test')
        self.client.logout()
        self.assertEqual(self.client.get('/invitation/'+pm_token+'/').status_code,200)
        self.assertEqual(self.client.post('/invitation/'+pm_token+'/',{'new_password1':self.password,'new_password2':self.password}).status_code,302)
        pm = User.objects.get(email='sarah@example.test')
        self.assertEqual(pm.membership.role,Membership.PM)
        self.client.post('/properties/new/',{'name':'Unit 12','address':'12 Oak Lane','access_responsibility':'sevlink','manager':admin.pk,'agency':'forged'})
        p = Property.objects.get(name='Unit 12')
        self.assertEqual(p.manager,pm)
        self.assertEqual(p.agency,pm.membership.agency)
        self.client.post(f'/properties/{p.pk}/tenant/',{'name':'Tenant','email':'tenant@example.test','phone':'0820000000'})
        token = self.token('tenant@example.test')
        self.client.logout()
        self.client.post('/invitation/'+token+'/',{'new_password1':self.password,'new_password2':self.password,'role':'admin'})
        tenant = User.objects.get(email='tenant@example.test')
        self.assertEqual(tenant.membership.role,Membership.TENANT)
        self.assertEqual(Tenancy.objects.get(email=tenant.email).user,tenant)
        self.assertContains(self.client.get('/'),'12 Oak Lane')
        self.assertNotContains(self.client.get('/'),'Invite property manager')
        self.assertEqual(self.client.post('/properties/new/',{}).status_code,403)
        self.assertEqual(self.client.post('/team/invite/',{}).status_code,403)
        self.client.logout()
        self.assertEqual(self.client.get('/invitation/'+token+'/').status_code,410)
        self.assertGreater(Audit.objects.count(),4)
    def test_portfolio_and_agency_isolation(self):
        a = Agency.objects.create(name='Agency A',phone='1',area='A')
        b = Agency.objects.create(name='Agency B',phone='2',area='B')
        owner = self.new_user('owner@example.test',a,Membership.ADMIN)
        pm1 = self.new_user('pm1@example.test',a,Membership.PM)
        pm2 = self.new_user('pm2@example.test',a,Membership.PM)
        foreign_pm = self.new_user('foreign@example.test',b,Membership.PM)
        p1 = Property.objects.create(agency=a,manager=pm1,name='One',address='VISIBLE ADDRESS')
        p2 = Property.objects.create(agency=a,manager=pm2,name='Two',address='OTHER PM ADDRESS')
        p3 = Property.objects.create(agency=b,manager=foreign_pm,name='Three',address='FOREIGN ADDRESS')
        self.client.force_login(pm1)
        page = self.client.get('/?setup=1')
        self.assertContains(page,'VISIBLE ADDRESS')
        self.assertNotContains(page,'OTHER PM ADDRESS')
        self.assertNotContains(page,'FOREIGN ADDRESS')
        for prop in [p2,p3]:
            self.assertEqual(self.client.get(f'/properties/{prop.pk}/edit/').status_code,404)
            self.assertEqual(self.client.post(f'/properties/{prop.pk}/tenant/',{'name':'Bad','email':'bad@example.test'}).status_code,404)
        self.assertEqual(self.client.get('/team/invite/').status_code,403)
        self.client.force_login(owner)
        self.assertContains(self.client.get('/?setup=1'),'OTHER PM ADDRESS')
        response = self.client.post(f'/properties/{p1.pk}/edit/',{'name':'One','address':'VISIBLE ADDRESS','manager':foreign_pm.pk,'access_responsibility':'sevlink'})
        self.assertEqual(response.status_code,200)
        p1.refresh_from_db()
        self.assertEqual(p1.manager,pm1)
    def test_expired_and_reissued_tokens(self):
        self.register()
        old = self.token('owner@example.test')
        self.client.post('/verify/resend/',{'email':'owner@example.test'})
        new = self.token('owner@example.test')
        self.assertNotEqual(old,new)
        self.assertEqual(self.client.get('/invitation/'+old+'/').status_code,410)
        Invitation.objects.filter(token_hash=digest(new)).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.client.post('/invitation/'+new+'/').status_code,410)
        self.assertFalse(User.objects.get(email='owner@example.test').is_active)
    def test_tenant_cannot_see_cotenant_details_or_private_access_notes(self):
        a = Agency.objects.create(name='Agency',phone='1',area='A')
        u = self.new_user('tenant@example.test',a,Membership.TENANT)
        p = Property.objects.create(agency=a,name='Home',address='HOME',access_notes='PRIVATE KEY SAFE 9977')
        Tenancy.objects.create(property=p,user=u,name='Me',email=u.email,phone='1')
        Tenancy.objects.create(property=p,name='PRIVATE COTENANT',email='other@example.test',phone='2')
        self.client.force_login(u)
        page = self.client.get('/?setup=1')
        self.assertNotContains(page,'PRIVATE COTENANT')
        self.assertNotContains(page,'PRIVATE KEY SAFE')
    def test_csrf_logout_and_login_throttle(self):
        strict = Client(enforce_csrf_checks=True)
        self.assertEqual(strict.post('/register/',{}).status_code,403)
        for _ in range(10):
            self.assertEqual(self.client.post('/login/',{'username':'missing@example.test','password':'bad'}).status_code,200)
        self.assertEqual(self.client.post('/login/',{'username':'missing@example.test','password':'bad'}).status_code,429)
        self.assertEqual(self.client.get('/logout/').status_code,405)
    def test_password_reset_queues_message_without_sending(self):
        a = Agency.objects.create(name='Agency',phone='1',area='A')
        u = self.new_user('reset@example.test',a,Membership.ADMIN)
        with override_settings(EMAIL_BACKEND='portal.mail.QueueBackend'):
            self.assertEqual(self.client.post('/password/reset/',{'email':u.email}).status_code,302)
        self.assertIn('https://portal.example.test/password/reset/',MailQueue.objects.get().body)
