"""Verify the additive Phase 1 migration preserves existing onboarding records."""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class MaintenanceMigrationTests(TransactionTestCase):
    def test_upgrade_preserves_existing_agency_property_and_tenancy(self):
        old = [('portal', '0001_initial')]
        new = [('portal', '0002_maintenancerequest_maintenancestatusevent_and_more')]
        try:
            executor = MigrationExecutor(connection)
            executor.migrate(old)
            apps = executor.loader.project_state(old).apps
            User = apps.get_model('portal', 'User')
            Agency = apps.get_model('portal', 'Agency')
            Property = apps.get_model('portal', 'Property')
            Membership = apps.get_model('portal', 'Membership')
            Tenancy = apps.get_model('portal', 'Tenancy')
            user = User.objects.create(username='migration@example.test', email='migration@example.test', password='!')
            agency = Agency.objects.create(name='Existing agency', phone='test', area='Test')
            Membership.objects.create(user=user, agency=agency, role='tenant')
            prop = Property.objects.create(agency=agency, name='Existing property', address='Existing address')
            tenancy = Tenancy.objects.create(property=prop, user=user, name='Existing tenant', email=user.email, phone='test')
            executor = MigrationExecutor(connection)
            executor.migrate(new)
            apps = executor.loader.project_state(new).apps
            self.assertEqual(apps.get_model('portal', 'User').objects.get(pk=user.pk).email, user.email)
            self.assertEqual(apps.get_model('portal', 'Agency').objects.get(pk=agency.pk).name, agency.name)
            self.assertEqual(apps.get_model('portal', 'Property').objects.get(pk=prop.pk).address, prop.address)
            self.assertEqual(apps.get_model('portal', 'Tenancy').objects.get(pk=tenancy.pk).user_id, user.pk)
            self.assertEqual(apps.get_model('portal', 'Membership').objects.get(user_id=user.pk).agency_id, agency.pk)
            self.assertEqual(apps.get_model('portal', 'MaintenanceRequest').objects.count(), 0)
        finally:
            MigrationExecutor(connection).migrate(new)
