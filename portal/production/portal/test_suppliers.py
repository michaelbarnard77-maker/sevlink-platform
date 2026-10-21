import json
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (AssignmentReview, AssignmentReviewResolution, ComplianceDocument, JobAssignment,
    MaintenanceRequest, Subcontractor, SubcontractorBank, SubcontractorTeam, SubcontractorTerms,
    SupplierActivity, TeamAppointment, TradeCategory, User)
from .suppliers import can_finance
from .test_attachments import document, photo
from .test_regions import fixtures, assign, SETTINGS


def post(client, name, data, *args):
    return client.post(reverse(name,args=args),json.dumps(data),content_type='application/json')


def team(client, supplier, **overrides):
    return post(client,'supplier_team',{**dict(version=0,name='Team A',active=True,working_days=[0,1,2,3,4],day_start='09:00',day_end='17:00'),**overrides},supplier.pk)


def assignment(client, job, supplier, crew):
    return post(client,'operations_assignments',{'subcontractor':str(supplier.pk),'version':job.version,
        'submission_key':str(uuid.uuid4()),'team':str(crew.pk)},job.pk)


def slots():
    day=timezone.localdate()+timedelta(days=7)
    day+=timedelta(days=(0-day.weekday())%7)
    start=datetime.combine(day,datetime.min.time(),tzinfo=ZoneInfo('Africa/Johannesburg')).replace(hour=10)
    return start,start+timedelta(hours=1)


def booking(client,supplier,allocation,start=None,end=None):
    default_start,default_end=slots()
    return post(client,'supplier_appointment',{'assignment':allocation.pk,
        'starts_at':(start or default_start).isoformat(),'ends_at':(end or default_end).isoformat()},supplier.pk)


@override_settings(**SETTINGS)
class SupplierTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        fixtures(cls)
        TradeCategory.objects.get_or_create(name='Plumbing')

    def setUp(self):
        self.client.force_login(self.ops)
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        self.root=Path(directory.name)
        override=override_settings(PRIVATE_ATTACHMENT_ROOT=directory.name,STORAGES={**settings.STORAGES,
            'maintenance_private':{'BACKEND':'portal.attachment_storage.PrivateAttachmentStorage','OPTIONS':{'location':directory.name}}})
        override.enable();self.addCleanup(override.disable)

    def profile_body(self,**overrides):
        return {**dict(name=self.partner.name,version=1,status='active',trades=['Plumbing'],
            contact_person='Synthetic contact',telephone='+27 00 000 0000',whatsapp='+27 00 000 0000',
            email='synthetic@example.test',specialisations='Private test specialisation',internal_notes='PRIVATE TEST NOTE'),**overrides}

    def get_profile(self): return self.client.get(reverse('supplier_profile',args=[self.partner.pk]))

    def upload(self,**overrides):
        return self.client.post(reverse('supplier_document_upload',args=[self.partner.pk]),
            {**dict(kind='insurance',title='Synthetic insurance',expires_on=str(timezone.localdate()+timedelta(days=15)),
                attachments=document(),submission_key=str(uuid.uuid4())),**overrides})

    def create_team_assignment(self):
        response=team(self.client,self.partner);self.assertEqual(response.status_code,200,response.content)
        crew=SubcontractorTeam.objects.get(pk=response.json()['id'])
        response=assignment(self.client,self.job,self.partner,crew);self.assertEqual(response.status_code,201,response.content)
        return crew,JobAssignment.objects.get(pk=response.json()['id'])

    def test_profile_fields_trades_status_and_optimistic_version(self):
        response=post(self.client,'supplier_profile',self.profile_body(),self.partner.pk)
        self.assertEqual(response.status_code,200,response.content)
        data=response.json();self.assertEqual(data['contact_person'],'Synthetic contact')
        self.assertEqual(data['trades'],['Plumbing']);self.assertEqual(data['version'],2)
        self.assertEqual(post(self.client,'supplier_profile',self.profile_body(),self.partner.pk).status_code,409)
        for status in ('inactive','archived','active'):
            data=post(self.client,'supplier_profile',self.profile_body(version=data['version'],status=status),self.partner.pk).json()
            self.assertEqual(data['status'],status)
            self.assertEqual(data['active'],status=='active')
        self.assertEqual(self.partner.agreements.count(),0)

    def test_profile_invalid_email_trade_and_unsupported_fields(self):
        for values in ({'email':'invalid'},{'trades':['Not a trade']},{'status':'deleted'},{'telephone':True},{'bank_name':'injected'}):
            self.assertEqual(post(self.client,'supplier_profile',self.profile_body(**values),self.partner.pk).status_code,400)

    def test_search_trade_status_filters(self):
        post(self.client,'supplier_profile',self.profile_body(),self.partner.pk)
        for filters in ({'search':'Synthetic contact'},{'search':'synthetic@example.test'},{'trade':'Plumbing'}):
            data=self.client.get(reverse('operations_regions'),filters).json()
            self.assertEqual([x['id'] for x in data['subcontractors']['results']],[str(self.partner.pk)])
        post(self.client,'supplier_profile',self.profile_body(version=2,status='archived'),self.partner.pk)
        data=self.client.get(reverse('operations_regions'),{'status':'archived'}).json()
        self.assertEqual([x['id'] for x in data['subcontractors']['results']],[str(self.partner.pk)])
        self.assertEqual(assign(self.client,self.job,self.partner).status_code,400)

    def test_finance_requires_explicit_grant_even_for_superadmin(self):
        body=dict(bank_name='SYNTHETIC BANK',account_holder='TEST HOLDER',account_number='12345678901',branch_code='123456',account_type='Cheque',version=0)
        self.assertFalse(can_finance(self.ops))
        self.assertEqual(post(self.client,'supplier_bank',body,self.partner.pk).status_code,403)
        permission=Permission.objects.get(codename='manage_subcontractor_finance')
        self.ops.user_permissions.add(permission)
        self.assertEqual(post(self.client,'supplier_bank',body,self.partner.pk).status_code,200)
        self.assertEqual(self.client.get(reverse('supplier_bank',args=[self.partner.pk])).json()['account_number'],body['account_number'])
        self.assertEqual(post(self.client,'supplier_bank',body,self.partner.pk).status_code,409)
        for url in (reverse('supplier_profile',args=[self.partner.pk]),reverse('operations_regions')):
            text=self.client.get(url).content.decode()
            self.assertNotIn(body['account_number'],text);self.assertNotIn(body['bank_name'],text)
        self.assertNotIn(body['account_number'],json.dumps(list(SupplierActivity.objects.values('details'))))
        self.ops.user_permissions.remove(permission)
        self.assertEqual(self.client.get(reverse('supplier_bank',args=[self.partner.pk])).status_code,403)
        self.pm.user_permissions.add(permission);self.client.force_login(self.pm)
        self.assertEqual(self.client.get(reverse('supplier_bank',args=[self.partner.pk])).status_code,403)

    def test_commercial_terms_are_decimal_append_only_and_idempotent(self):
        data=dict(commission_percent='12.50',rate='450.25',rate_basis='hour',terms='PRIVATE negotiated terms',submission_key=str(uuid.uuid4()))
        response=post(self.client,'supplier_agreement',data,self.partner.pk)
        self.assertEqual(response.status_code,201,response.content)
        self.assertEqual(post(self.client,'supplier_agreement',data,self.partner.pk).status_code,200)
        self.assertEqual(post(self.client,'supplier_agreement',{**data,'rate':'451.25'},self.partner.pk).status_code,409)
        entry=SubcontractorTerms.objects.get();self.assertEqual(str(entry.rate),'450.25')
        with self.assertRaises(ValidationError): entry.delete()
        for changes in ({'commission_percent':'100.01'},{'rate':'1.001'},{'rate':'NaN'},{'rate':'-1'}):
            self.assertEqual(post(self.client,'supplier_agreement',{**data,**changes,'submission_key':str(uuid.uuid4())},self.partner.pk).status_code,400)

    def test_private_pdf_upload_download_headers_storage_and_replacement(self):
        response=self.upload();self.assertEqual(response.status_code,201,response.content)
        doc=ComplianceDocument.objects.get()
        self.assertTrue(doc.storage_key.startswith('subcontractors/'))
        self.assertEqual((self.root/doc.storage_key).stat().st_mode & 0o777,0o600)
        response=self.client.get(response.json()['url'])
        self.assertEqual(response.status_code,200)
        self.assertTrue(b''.join(response.streaming_content).startswith(b'%PDF-'))
        self.assertIn('no-store',response['Cache-Control']);self.assertIn('sandbox',response['Content-Security-Policy'])
        replacement=self.upload(previous=str(doc.pk),title='Replacement',expires_on='')
        self.assertEqual(replacement.status_code,201,replacement.content)
        self.assertEqual(ComplianceDocument.objects.count(),2)
        self.assertTrue(self.get_profile().json()['documents'][1]['superseded'])
        self.assertEqual(self.client.get(reverse('supplier_document_pdf',args=[self.inland.pk,doc.pk])).status_code,404)
        self.assertEqual(self.upload(previous=str(doc.pk)).status_code,409)
        with self.assertRaises(ValidationError): doc.delete()

    def test_document_limits_invalid_files_expiry_and_duplicate_upload(self):
        key=str(uuid.uuid4())
        self.assertEqual(self.upload(submission_key=key).status_code,201)
        self.assertEqual(self.upload(submission_key=key).status_code,200)
        self.assertEqual(ComplianceDocument.objects.count(),1)
        self.assertEqual(self.upload(submission_key=key,title='Changed').status_code,409)
        self.assertEqual(self.upload(attachments=photo()).status_code,400)
        self.assertEqual(self.upload(expires_on='not-a-date').status_code,400)
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.assertEqual(self.upload(attachments=SimpleUploadedFile('huge.pdf',b'x'*(5*1024*1024+1),'application/pdf')).status_code,400)
        self.assertEqual(self.upload(attachments=SimpleUploadedFile('bad.pdf',b'%PDF-fake','application/pdf')).status_code,400)

    def test_pdf_database_failure_removes_orphaned_file(self):
        with patch('portal.suppliers.ComplianceDocument.objects.create',side_effect=RuntimeError('synthetic failure')):
            with self.assertRaises(RuntimeError): self.upload()
        self.assertEqual(list(self.root.rglob('*.pdf')),[])
        self.assertEqual(ComplianceDocument.objects.count(),0)

    def test_expiry_reminders_boundaries_and_superseded_documents(self):
        today=timezone.localdate()
        for days,state in [(-1,'expired'),(0,'expiring_soon'),(30,'expiring_soon'),(31,'current')]:
            response=self.upload(expires_on=str(today+timedelta(days=days)))
            self.assertEqual(response.json()['state'],state)
        response=self.upload(expires_on='');self.assertEqual(response.json()['state'],'no_expiry_recorded')
        alerts=self.client.get(reverse('operations_regions')).json()['compliance_alerts']
        self.assertEqual(alerts['count'],3)
        expired=ComplianceDocument.objects.get(expires_on=today-timedelta(days=1))
        self.assertEqual(self.upload(previous=str(expired.pk),expires_on=str(today+timedelta(days=365))).status_code,201)
        self.assertEqual(self.client.get(reverse('operations_regions')).json()['compliance_alerts']['count'],2)

    def test_non_operations_cannot_access_profiles_documents_finance_or_teams(self):
        doc=self.upload().json();team_response=team(self.client,self.partner).json()
        staff=User.objects.create_user(username='supplier-staff',email='supplier-staff@example.test',is_staff=True)
        outsider=User.objects.create_user(username='supplier-private',email='supplier-private@example.test')
        for user in (self.pm,self.tenant,staff,outsider):
            self.client.force_login(user)
            for endpoint in ('supplier_profile','supplier_bank'):
                self.assertEqual(self.client.get(reverse(endpoint,args=[self.partner.pk])).status_code,403)
            self.assertEqual(self.client.get(doc['url']).status_code,403)
            self.assertEqual(post(self.client,'supplier_team',{},self.partner.pk).status_code,403)
            self.assertEqual(post(self.client,'supplier_unavailable',{},self.partner.pk,team_response['id']).status_code,403)
            self.assertEqual(post(self.client,'supplier_agreement',{},self.partner.pk).status_code,403)
            self.assertEqual(post(self.client,'supplier_appointment',{},self.partner.pk).status_code,403)

    def test_private_supplier_information_never_enters_external_job_json(self):
        post(self.client,'supplier_profile',self.profile_body(),self.partner.pk)
        crew,allocation=self.create_team_assignment();self.upload()
        post(self.client,'supplier_agreement',dict(commission_percent='12.50',rate='450.25',rate_basis='hour',terms='PRIVATE AGREEMENT',submission_key=str(uuid.uuid4())),self.partner.pk)
        for user in (self.pm,self.tenant):
            self.client.force_login(user)
            text=self.client.get(reverse('maintenance_detail',args=[self.job.pk])).content.decode()
            for secret in ('PRIVATE TEST NOTE','synthetic@example.test','PRIVATE AGREEMENT','450.25',str(crew.pk),str(self.partner.pk),'subcontractor_id'):
                self.assertNotIn(secret,text)
            self.assertEqual(self.client.get(reverse('maintenance_detail',args=[self.cape_job.pk])).status_code,404)

    def test_multiple_teams_require_explicit_team_and_compatible_parent(self):
        first=team(self.client,self.partner).json()
        second=team(self.client,self.partner,name='Team B').json()
        self.assertEqual(self.partner.teams.count(),2)
        self.assertEqual(assign(self.client,self.job,self.partner).status_code,400)
        wrong=team(self.client,self.inland).json()
        self.assertEqual(assignment(self.client,self.job,self.partner,SubcontractorTeam.objects.get(pk=wrong['id'])).status_code,404)
        crew=SubcontractorTeam.objects.get(pk=first['id'])
        self.assertEqual(assignment(self.client,self.job,self.partner,crew).status_code,201)
        self.job.refresh_from_db()
        other=SubcontractorTeam.objects.get(pk=second['id'])
        self.assertEqual(assignment(self.client,self.job,self.partner,other).status_code,201)
        self.assertEqual(JobAssignment.objects.count(),2)

    def test_legacy_assignments_remain_unallocated_when_teams_added(self):
        self.assertEqual(assign(self.client,self.job,self.partner).status_code,201)
        original=JobAssignment.objects.get();self.assertIsNone(original.team_id)
        team(self.client,self.partner)
        original.refresh_from_db();self.assertIsNone(original.team_id)
        self.assertEqual(JobAssignment.objects.count(),1)
        self.assertEqual(booking(self.client,self.partner,original).status_code,400)

    def test_team_validation_empty_days_stale_versions_and_duplicate_names(self):
        response=team(self.client,self.partner,working_days=[])
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(team(self.client,self.partner,name='team a').status_code,400)
        crew=SubcontractorTeam.objects.get(pk=response.json()['id'])
        body=dict(id=str(crew.pk),version=0,name='Team A',active=True,working_days=[0],day_start='09:00',day_end='17:00')
        self.assertEqual(post(self.client,'supplier_team',body,self.partner.pk).status_code,409)
        for values in ({'working_days':[True]},{'working_days':[0,0]},{'day_end':'08:00'},{'day_start':'08:00'}):
            self.assertEqual(team(self.client,self.partner,name='Invalid',**values).status_code,400)

    def test_appointments_unavailable_dates_overlap_and_manual_cancellation(self):
        crew,allocation=self.create_team_assignment();start,end=slots()
        response=booking(self.client,self.partner,allocation);self.assertEqual(response.status_code,201,response.content)
        self.assertEqual(booking(self.client,self.partner,allocation).status_code,200)
        self.assertEqual(post(self.client,'supplier_unavailable',dict(date=str(start.date()),reason='Unavailable'),self.partner.pk,crew.pk).status_code,409)
        crew.refresh_from_db()
        body=dict(id=str(crew.pk),version=crew.version,name=crew.name,active=False,working_days=[0],day_start='09:00',day_end='17:00')
        self.assertEqual(post(self.client,'supplier_team',body,self.partner.pk).status_code,409)
        entry=TeamAppointment.objects.get()
        response=post(self.client,'supplier_appointment',dict(cancel=entry.pk,reason='Test reschedule'),self.partner.pk)
        self.assertEqual(response.status_code,200)
        self.assertEqual(post(self.client,'supplier_unavailable',dict(date=str(start.date()),reason='Unavailable'),self.partner.pk,crew.pk).status_code,200)
        self.assertEqual(booking(self.client,self.partner,allocation).status_code,400)
        self.assertEqual(post(self.client,'supplier_unavailable',dict(date=str(start.date()),remove=True),self.partner.pk,crew.pk).status_code,200)
        self.assertEqual(booking(self.client,self.partner,allocation).status_code,201)
        self.assertEqual(TeamAppointment.objects.count(),2)

    def test_different_teams_can_work_simultaneously_and_same_team_cannot(self):
        crew,allocation=self.create_team_assignment()
        second=SubcontractorTeam.objects.get(pk=team(self.client,self.partner,name='Team B').json()['id'])
        self.assertEqual(assignment(self.client,self.cape_job,self.partner,second).status_code,201)
        other=JobAssignment.objects.get(request=self.cape_job)
        self.assertEqual(booking(self.client,self.partner,allocation).status_code,201)
        self.assertEqual(booking(self.client,self.partner,other).status_code,201)
        third_job=MaintenanceRequest.objects.create(property=self.home,reported_by=self.tenant,title='Another',description='Test',category='Plumbing')
        self.assertEqual(assignment(self.client,third_job,self.partner,crew).status_code,201)
        third=JobAssignment.objects.get(request=third_job)
        self.assertEqual(booking(self.client,self.partner,third).status_code,409)
        start,end=slots()
        self.assertEqual(booking(self.client,self.partner,third,start=end,end=end+timedelta(hours=1)).status_code,201)

    def test_location_coverage_and_status_changes_flag_preserved_assignments(self):
        crew,allocation=self.create_team_assignment()
        response=post(self.client,'operations_property_location',dict(city=self.cape.pk,suburb=self.sea.pk),self.home.pk)
        self.assertEqual(response.status_code,200)
        self.assertEqual(AssignmentReview.objects.count(),1)
        self.assertEqual(booking(self.client,self.partner,allocation).status_code,409)
        body=dict(id=str(self.partner.pk),name=self.partner.name,active=True,provinces=[],cities=[self.cape.pk],suburbs=[])
        self.assertEqual(post(self.client,'operations_subcontractor',body).status_code,200)
        self.assertEqual(AssignmentReview.objects.count(),2)
        post(self.client,'supplier_profile',self.profile_body(version=2,status='archived'),self.partner.pk)
        self.assertEqual(AssignmentReview.objects.count(),3)
        self.assertEqual(JobAssignment.objects.count(),1)
        allocation.refresh_from_db();self.assertEqual(allocation.city_id,self.joburg.pk)
        for review in AssignmentReview.objects.all():
            self.assertEqual(post(self.client,'supplier_assignment_review',{'reason':'Reviewed manually'},review.pk).status_code,200)
            self.assertEqual(post(self.client,'supplier_assignment_review',{'reason':'Again'},review.pk).status_code,409)
        self.assertEqual(AssignmentReviewResolution.objects.count(),3)

    def test_working_hours_days_and_aware_datetimes_are_enforced(self):
        crew,a=self.create_team_assignment();start,end=slots()
        self.assertEqual(booking(self.client,self.partner,a,start=start.replace(hour=8),end=end).status_code,400)
        self.assertEqual(booking(self.client,self.partner,a,start=start+timedelta(days=6),end=end+timedelta(days=6)).status_code,400)
        self.assertEqual(post(self.client,'supplier_appointment',dict(assignment=a.pk,starts_at='2030-01-01T10:00',ends_at='2030-01-01T11:00'),self.partner.pk).status_code,400)
        client=Client(enforce_csrf_checks=True);client.force_login(self.ops)
        self.assertEqual(team(client,self.partner).status_code,403)


@override_settings(**SETTINGS)
@skipUnless(connection.vendor=='postgresql','PostgreSQL row locking')
class SupplierConcurrencyTests(TransactionTestCase):
    def setUp(self):
        fixtures(self)
        self.crew=SubcontractorTeam.objects.create(subcontractor=self.partner,name='Team A',working_days=[0,1,2,3,4])
        # Model defaults are coerced by the DB before availability checks.
        self.crew.refresh_from_db()
        self.allocations=[JobAssignment.objects.create(request=j,subcontractor=self.partner,team=self.crew,actor=self.ops,city=j.property.city,submission_key=uuid.uuid4()) for j in (self.job,self.cape_job)]

    def test_concurrent_same_team_appointments_cannot_overlap(self):
        def action(pk):
            try:
                client=Client();client.force_login(User.objects.get(pk=self.ops.pk))
                return booking(client,self.partner,JobAssignment.objects.get(pk=pk)).status_code
            finally:
                connections.close_all()
                for alias in connections:self.assertIsNone(connections[alias].connection)
        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses=list(executor.map(action,[a.pk for a in self.allocations]))
        self.assertEqual(sorted(statuses),[201,409])
        self.assertEqual(TeamAppointment.objects.count(),1)


class SupplierMigrationTests(TransactionTestCase):
    def test_preserves_historical_unallocated_assignment_and_inactive_supplier(self):
        old=[('portal','0015_seed_sa_regions')];new=[('portal','0017_seed_supplier_trades')]
        try:
            MigrationExecutor(connection).migrate(old)
            apps=MigrationExecutor(connection).loader.project_state(old).apps
            user=apps.get_model('portal','User').objects.create(username='legacy-supplier',email='legacy-supplier@example.test',password='!')
            agency=apps.get_model('portal','Agency').objects.create(name='Legacy',phone='test',area='Gauteng')
            province,_=apps.get_model('portal','Province').objects.get_or_create(code='GP',defaults={'name':'Gauteng'})
            city,_=apps.get_model('portal','City').objects.get_or_create(name='Meyerton',province=province)
            prop=apps.get_model('portal','Property').objects.create(agency=agency,name='Legacy',address='Original address',city=city)
            job=apps.get_model('portal','MaintenanceRequest').objects.create(property=prop,reported_by=user,title='Legacy',description='Test',category='Plumbing')
            supplier=apps.get_model('portal','Subcontractor').objects.create(name='Existing inactive',active=False,created_by=user)
            allocation=apps.get_model('portal','JobAssignment').objects.create(request=job,subcontractor=supplier,actor=user,city=city,submission_key=uuid.uuid4())
            MigrationExecutor(connection).migrate(new)
            apps=MigrationExecutor(connection).loader.project_state(new).apps
            actual=apps.get_model('portal','JobAssignment').objects.get(pk=allocation.pk)
            self.assertIsNone(actual.team_id);self.assertEqual(actual.city_id,city.pk)
            supplier=apps.get_model('portal','Subcontractor').objects.get(pk=supplier.pk)
            self.assertFalse(supplier.active);self.assertFalse(supplier.archived)
            self.assertEqual(supplier.email,'');self.assertEqual(apps.get_model('portal','TradeCategory').objects.count(),19)
        finally:MigrationExecutor(connection).migrate(new)
