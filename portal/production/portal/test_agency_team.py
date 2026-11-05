from django.test import TestCase, override_settings
from django.urls import reverse
from .test_notifications import EventWorkflowTests
from .models import Property


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class AgencyTeamTests(TestCase):
    setUpTestData = classmethod(EventWorkflowTests.setUpTestData.__func__)

    def profile(self, user):
        self.client.force_login(user)
        return self.client.get(reverse('customer_portal_section', args=['profile']))

    def test_admin_sees_only_own_agency_team_and_controls(self):
        result = self.profile(self.admin).json()
        self.assertEqual(result['invite_agent_url'], reverse('invite_pm'))
        self.assertEqual({r['email'] for r in result['team']}, {self.pm.email, self.other_pm.email})
        self.assertNotIn(self.foreign.email, str(result))
        self.assertEqual(next(r for r in result['team'] if r['email'] == self.pm.email)['properties'], 1)

    def test_agent_has_no_team_controls_or_other_agents_properties(self):
        self.assertEqual(self.profile(self.pm).status_code, 403)
        self.assertEqual(self.profile(self.tenant).status_code, 403)
        self.client.force_login(self.pm)
        self.assertEqual(self.client.get(reverse('invite_pm')).status_code, 403)
        other = Property.objects.create(agency=self.agency, manager=self.other_pm, name='Other agent', address='Private other agent address')
        result = self.client.get(reverse('customer_portal_section', args=['properties'])).json()
        self.assertEqual({r['id'] for r in result['properties']}, {str(self.home.pk)})
        self.assertEqual(self.client.get(reverse('property_edit', args=[other.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('invite_tenant', args=[other.pk])).status_code, 404)

    def test_agent_created_property_assigns_to_self_and_admin_can_reassign(self):
        self.client.force_login(self.pm)
        data = dict(name='Agent own property', address='14 Example Street', access_responsibility='agency', access_notes='Call first')
        response = self.client.post(reverse('property_new'), data)
        self.assertEqual(response.status_code, 302)
        prop = Property.objects.get(name=data['name'])
        self.assertEqual(prop.manager_id, self.pm.pk)
        self.client.force_login(self.admin)
        response = self.client.post(reverse('property_edit', args=[prop.pk]), {**data, 'manager':str(self.other_pm.pk)})
        self.assertEqual(response.status_code, 302)
        prop.refresh_from_db()
        self.assertEqual(prop.manager_id, self.other_pm.pk)
        self.client.force_login(self.pm)
        self.assertEqual(self.client.get(reverse('property_edit', args=[prop.pk])).status_code, 404)
