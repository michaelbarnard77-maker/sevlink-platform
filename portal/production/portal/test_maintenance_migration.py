"""Verify the additive Phase 1 migration preserves existing onboarding records."""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class MaintenanceMigrationTests(TransactionTestCase):
    def test_upgrade_preserves_existing_agency_property_and_tenancy(self):
        old = [('portal', '0001_initial')]
        new = [('portal', '0017_seed_supplier_trades')]
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
            phase1 = [('portal', '0002_maintenancerequest_maintenancestatusevent_and_more')]
            executor = MigrationExecutor(connection)
            executor.migrate(phase1)
            phase1_apps = executor.loader.project_state(phase1).apps
            job = phase1_apps.get_model('portal', 'MaintenanceRequest').objects.create(
                property_id=prop.pk, reported_by_id=user.pk, title='Existing repair',
                description='Existing report', category='Plumbing', internal_notes='Internal test note')
            phase1_apps.get_model('portal', 'MaintenanceStatusEvent').objects.create(
                request_id=job.pk, actor_id=user.pk, status='awaiting_review')
            executor = MigrationExecutor(connection)
            executor.migrate(new)
            apps = executor.loader.project_state(new).apps
            self.assertEqual(apps.get_model('portal', 'User').objects.get(pk=user.pk).email, user.email)
            self.assertEqual(apps.get_model('portal', 'Agency').objects.get(pk=agency.pk).name, agency.name)
            self.assertEqual(apps.get_model('portal', 'Property').objects.get(pk=prop.pk).address, prop.address)
            self.assertEqual(apps.get_model('portal', 'Tenancy').objects.get(pk=tenancy.pk).user_id, user.pk)
            self.assertEqual(apps.get_model('portal', 'Membership').objects.get(user_id=user.pk).agency_id, agency.pk)
            self.assertEqual(apps.get_model('portal', 'MaintenanceRequest').objects.get(pk=job.pk).title, 'Existing repair')
            self.assertEqual(apps.get_model('portal', 'MaintenanceStatusEvent').objects.get(request_id=job.pk).status, 'awaiting_review')
            self.assertEqual(apps.get_model('portal', 'MaintenanceAttachment').objects.count(), 0)
            self.assertEqual(apps.get_model('portal', 'JobActivity').objects.get(request_id=job.pk).actor_id, user.pk)
            self.assertEqual(apps.get_model('portal', 'OperationsNotification').objects.count(), 0)
        finally:
            MigrationExecutor(connection).migrate(new)


class QuotationUpgradeTests(TransactionTestCase):
    def test_upgrade_preserves_pending_decided_quotes_and_existing_outbox(self):
        import uuid
        from django.utils import timezone
        old = [('portal', '0006_maintenancerequest_submission_fingerprint_and_more')]
        new = [('portal', '0017_seed_supplier_trades')]
        try:
            executor = MigrationExecutor(connection); executor.migrate(old)
            apps = executor.loader.project_state(old).apps
            user = apps.get_model('portal','User').objects.create(username='legacy@example.test',email='legacy@example.test',password='!')
            agency = apps.get_model('portal','Agency').objects.create(name='Legacy',phone='test',area='test')
            prop = apps.get_model('portal','Property').objects.create(agency=agency,name='Legacy home',address='Test')
            job = apps.get_model('portal','MaintenanceRequest').objects.create(property=prop,reported_by=user,title='Legacy job',description='Test',category='Plumbing')
            quote_ids=[]
            for status in ('pending','pending','approved','rejected'):
                quote=apps.get_model('portal','JobQuotation').objects.create(request=job,created_by=user,
                    creation_key=uuid.uuid4(),title='Legacy scope',scope='Preserve scope',amount='1234.50',status=status,
                    decided_by=user if status != 'pending' else None,
                    decided_at=timezone.now() if status != 'pending' else None,
                    decision_reason='Legacy decision' if status != 'pending' else '',
                    decision_key=uuid.uuid4() if status != 'pending' else None)
                quote_ids.append(quote.pk)
            event=apps.get_model('portal','JobActivity').objects.create(request=job,actor=user,actor_name='Legacy',actor_role='tenant',
                kind='job_submitted',dedup_key='legacy-submission',details={'status':'awaiting_review'},job_title=job.title,
                property_name=prop.name,property_address=prop.address,agency_name=agency.name)
            notice=apps.get_model('portal','OperationsNotification').objects.create(event=event,recipient='maintenance@sevlink.co.za',state='sent',attempts=1)
            executor=MigrationExecutor(connection);executor.migrate(new)
            apps=executor.loader.project_state(new).apps
            quotes=list(apps.get_model('portal','JobQuotation').objects.filter(pk__in=quote_ids))
            self.assertEqual(len({q.series_id for q in quotes}),4)
            self.assertEqual(sorted(q.status for q in quotes),['approved','rejected','sent','sent'])
            self.assertEqual(apps.get_model('portal','JobInvoice').objects.count(),0)
            for quote in quotes:
                self.assertIsNone(quote.document_id)
                self.assertEqual(quote.reference,'')
                self.assertEqual(str(quote.amount),'1234.50')
                self.assertEqual(quote.public_snapshot['amount'],'1234.50')
                self.assertEqual(quote.public_snapshot['scope'],'Preserve scope')
                self.assertEqual(apps.get_model('portal','QuotationLine').objects.get(quote=quote).total,quote.amount)
            self.assertEqual(apps.get_model('portal','QuotationAction').objects.count(),2)
            self.assertEqual(apps.get_model('portal','OperationsInboxItem').objects.get().event_id,event.pk)
            self.assertEqual(apps.get_model('portal','OperationsNotification').objects.get(pk=notice.pk).state,'sent')
        finally:
            MigrationExecutor(connection).migrate(new)
