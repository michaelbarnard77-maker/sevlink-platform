"""Optional real-browser workflow test; uses Django's isolated temporary test DB."""
import json
import os
from pathlib import Path
import subprocess
from unittest import skipUnless

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings

from .models import Agency, Membership, Property, Tenancy, User, MaintenanceRequest


@skipUnless(os.environ.get('SEVLINK_BROWSER_TESTS') == '1', 'Set SEVLINK_BROWSER_TESTS=1 with Node Playwright installed.')
@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class MaintenanceBrowserTests(StaticLiveServerTestCase):
    def test_tenant_submission_manager_update_and_relogin(self):
        agency = Agency.objects.create(name='Browser test agency', phone='test', area='Test')
        sessions = {}
        for role in ['tenant', 'pm', 'superadmin']:
            user = User.objects.create_user(username=role + '@example.test', email=role + '@example.test', first_name=role,
                                            is_staff=role == 'superadmin', is_superuser=role == 'superadmin')
            if role != 'superadmin':
                Membership.objects.create(user=user, agency=agency, role=role)
            client = Client()
            client.force_login(user)
            sessions[role] = client.cookies[settings.SESSION_COOKIE_NAME].value
        prop = Property.objects.create(agency=agency, manager=User.objects.get(first_name='pm'), name='Browser home', address='12 Test Road')
        tenant = User.objects.get(first_name='tenant')
        fresh_client = Client()
        fresh_client.force_login(tenant)
        sessions['tenantAgain'] = fresh_client.cookies[settings.SESSION_COOKIE_NAME].value
        Tenancy.objects.create(property=prop, user=tenant, name='Test tenant', email=tenant.email, phone='test')
        script = Path(settings.BASE_DIR).parents[1] / 'scripts' / 'test-maintenance-browser.cjs'
        result = subprocess.run(['node', str(script)], input=json.dumps({'url': self.live_server_url, 'sessions': sessions}),
                                text=True, capture_output=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS', result.stdout)
        self.assertEqual(MaintenanceRequest.objects.get().status, 'reviewed')
