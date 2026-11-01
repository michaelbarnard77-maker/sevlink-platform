from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.staticfiles import finders
from .models import User


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False, ALLOWED_HOSTS=['testserver'])
class LandingJourneyTests(TestCase):
    def test_public_home_links_to_same_tab_login_with_local_assets(self):
        response=self.client.get('/')
        self.assertContains(response,'Your property.')
        self.assertContains(response,'href="/login/"')
        self.assertNotContains(response,'sevlink-maintenance-demo')
        self.assertContains(response,'/static/landing/styles.css')
        for asset in ['styles.css','app.js','assets/hero-home.png','assets/sevlink-logo.png']:
            self.assertTrue(finders.find('landing/'+asset))
        self.assertRedirects(self.client.get('/portal/'),'/login/?next=/portal/',fetch_redirect_response=False)

    def test_login_enters_workspace_and_home_remains_landing(self):
        user=User.objects.create_superuser(username='ops@example.test',email='ops@example.test',password='Example-test-password-123!')
        response=self.client.post(reverse('login'),{'username':user.email,'password':'Example-test-password-123!'})
        self.assertRedirects(response,'/portal/',fetch_redirect_response=False)
        self.assertRedirects(self.client.get('/portal/'),reverse('maintenance_workspace'))
        self.assertContains(self.client.get('/'),'Your property.')
