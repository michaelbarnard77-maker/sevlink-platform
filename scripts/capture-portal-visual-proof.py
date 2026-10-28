"""Capture authenticated screens with synthetic data in an isolated temporary SQLite DB.
Run with the existing Django Python environment; requires Node Playwright/Chromium.
Set SEVLINK_VISUAL_PROOF_DIR to choose the output directory. No production services.
"""
import os,sys,tempfile,secrets,json,uuid,subprocess,base64
from pathlib import Path
from datetime import timedelta
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'portal/production'))
os.environ['DJANGO_SETTINGS_MODULE']='config.settings'
os.environ['DEBUG']='1'
os.environ.setdefault('DJANGO_SECRET_KEY',secrets.token_urlsafe(64))
os.environ['SMTP_DELIVERY_ENABLED']='0';os.environ['OPERATIONS_LIVE_DELIVERY_ENABLED']='0'
os.environ.pop('DB_HOST',None)
if Path('/opt/codex/runtimes/codex-primary-runtime/dependencies/node/node_modules').exists():
    os.environ.setdefault('NODE_PATH','/opt/codex/runtimes/codex-primary-runtime/dependencies/node/node_modules')
OUTPUT=Path(os.environ.get('SEVLINK_VISUAL_PROOF_DIR',str(Path(tempfile.gettempdir())/'sevlink-visual-proof'))).resolve()
TEMP=tempfile.TemporaryDirectory(prefix='sevlink-visual-proof-')
os.environ['SEVLINK_SQLITE_TEST_DATABASE']=str(Path(TEMP.name)/'test.sqlite3')
import django
django.setup()
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client,override_settings
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from portal.models import User,Agency,Membership,Province,City,Property,Tenancy,Subcontractor,SubcontractorTeam,TradeCategory,MaintenanceRequest,AttendanceRequest
from portal.test_attachments import document

@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False,ALLOWED_HOSTS=['testserver','localhost','127.0.0.1'],PRIVATE_ATTACHMENT_ROOT=Path(TEMP.name)/'private',STORAGES={**settings.STORAGES,'maintenance_private':{'BACKEND':'portal.attachment_storage.PrivateAttachmentStorage','OPTIONS':{'location':str(Path(TEMP.name)/'private')}}},EMAIL_FILE_PATH=Path(TEMP.name)/'email',OPERATIONS_LIVE_DELIVERY_ENABLED=False)
class VisualProof(StaticLiveServerTestCase):
    def post(self,user,url,values=None,files=None,method='POST'):
        self.client.force_login(user)
        if files is not None:r=self.client.post(url,{**(values or {}),**files},HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        elif method=='PATCH':r=self.client.patch(url,json.dumps(values),content_type='application/json')
        else:r=self.client.post(url,json.dumps(values or {}),content_type='application/json',HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertIn(r.status_code,(200,201),f'{url}: {r.status_code} {r.content[:800]}')
        return r.json()
    def action(self,user,job,op,**v):
        job.refresh_from_db()
        return self.post(user,reverse('workflow_action',args=[job.pk,op]),dict(version=job.version,**v))
    def create(self,title,category='Plumbing',safety=False):
        d=self.post(self.tenant,reverse('maintenance_collection'),dict(property=str(self.home.pk),title=title,description='Synthetic visual-review record. No actual customer job or service is represented.',category=category,urgency='safety' if safety else 'normal'))
        return MaintenanceRequest.objects.get(pk=d['id'])
    def quote(self,job,ref,approve=False):
        d=self.post(self.ops,reverse('maintenance_quote',args=[job.pk]),dict(reference=ref,amount='4000.00',title='Tap repair and testing — visual test',scope='Synthetic uploaded PDF for visual acceptance only.'),{'attachments':document(name=ref+'.pdf')})
        d=self.post(self.ops,reverse('maintenance_quote_action',args=[job.pk,d['id'],'send']),dict(version=d['version']))
        if approve:d=self.post(self.pm,reverse('maintenance_quote_decision',args=[job.pk,d['id']]),dict(version=d['version'],status='approved',reason='Synthetic visual-review approval only.'))
        return d
    def invoice(self,job,ref,purpose,amount,pay=False):
        d=self.post(self.ops,reverse('maintenance_invoice',args=[job.pk]),dict(number=ref,amount=amount,due_date=str(timezone.localdate()+timedelta(days=7)),visibility='shared',purpose=purpose),{'attachments':document(name=ref+'.pdf')})
        if pay:self.post(self.ops,reverse('maintenance_invoice_payment',args=[job.pk,d['id']]),dict(version=d['version'],amount=amount,paid_on=str(timezone.localdate()),reference='VISUAL-TEST-RECEIPT',note='Synthetic manual receipt in temporary test database only.'))
        return d
    def test_capture(self):
        from django.db import connection
        self.assertEqual(str(connection.settings_dict['NAME']),os.environ['SEVLINK_SQLITE_TEST_DATABASE'])
        self.ops=User.objects.create_user(username='operations-review',first_name='Operations Review',email='operations@example.test',is_staff=True,is_superuser=True)
        agency=Agency.objects.create(name='Visual review agency — test data',phone='Test only',area='Gauteng and Cape Town')
        self.pm=User.objects.create_user(username='pm-review',first_name='PM Review',email='pm@example.test');Membership.objects.create(user=self.pm,agency=agency,role='pm')
        self.tenant=User.objects.create_user(username='tenant-review',first_name='Tenant Review',email='tenant@example.test');Membership.objects.create(user=self.tenant,agency=agency,role='tenant')
        gp,_=Province.objects.get_or_create(code='GP',defaults={'name':'Gauteng'});city,_=City.objects.get_or_create(province=gp,name='Johannesburg')
        self.home=Property.objects.create(agency=agency,manager=self.pm,name='Visual test home',address='12 Example Road — test property',city=city)
        Tenancy.objects.create(property=self.home,user=self.tenant,name='Tenant Review',email='tenant@example.test',phone='Test only')
        supplier=Subcontractor.objects.create(name='PRIVATE TEST SUPPLIER',created_by=self.ops,internal_notes='PRIVATE TEST INFORMATION')
        supplier.cities.add(city);trade,_=TradeCategory.objects.get_or_create(name='Plumbing');supplier.trades.add(trade)
        team=SubcontractorTeam.objects.create(subcontractor=supplier,name='Private test team',working_days=list(range(7)))
        job=self.create('Kitchen tap repair — visual test')
        self.action(self.pm,job,'review',job_type='quoted',urgency='normal',access_responsibility='pm',access_information='Test access arrangement only.')
        self.quote(job,'SQ-VISUAL-001',True)
        self.invoice(job,'INV-VISUAL-DEPOSIT','deposit','2000.00',True)
        self.action(self.ops,job,'verify-deposit',confirmation='VERIFY')
        when=timezone.localdate()+timedelta(days=2)
        self.action(self.pm,job,'attendance-request',preference='date',date=str(when),window='09:00–13:00')
        arrival=AttendanceRequest.objects.get(request=job);job.refresh_from_db()
        self.post(self.ops,reverse('workflow_confirm_attendance',args=[job.pk]),dict(version=job.version,attendance=arrival.pk,date=str(when),window='09:00–13:00',subcontractor=str(supplier.pk),team=str(team.pk),starts_at=f'{when}T09:00:00+02:00',ends_at=f'{when}T10:00:00+02:00'))
        for purpose in ['completion_before','completion_after']:
            photo=SimpleUploadedFile(purpose+'-TEST-ILLUSTRATION.png',(ROOT/'public-site/dist/assets/hero-home.png').read_bytes(),content_type='image/png')
            self.post(self.ops,reverse('workflow_documents',args=[job.pk]),dict(kind=purpose),{'attachments':photo})
        self.action(self.ops,job,'completion',report='VISUAL TEST ONLY — no actual work was performed. The before and after images are the same existing website illustration, uploaded solely to demonstrate the report layout.',before_unavailable=False,exception_reason='')
        for status in ['on_site','attended','completed']:
            job.refresh_from_db();self.post(self.ops,reverse('maintenance_detail',args=[job.pk]),dict(version=job.version,status=status),method='PATCH')
        self.invoice(job,'INV-VISUAL-FINAL','final','2000.00')
        for user,body,visibility in [(self.tenant,'Please keep me informed about attendance. Visual test message.','shared'),(self.pm,'Please review the uploaded documents. Visual test message.','agency'),(self.ops,'The report and final invoice are available for review. Visual test message.','shared'),(self.ops,'PRIVATE TEST INFORMATION — Operations only.','internal')]:
            self.post(user,reverse('maintenance_comment',args=[job.pk]),dict(text=body,visibility=visibility))
        pending=self.create('Bathroom tap quotation — visual test');self.action(self.pm,pending,'review',job_type='quoted',urgency='high',access_responsibility='sevlink');self.quote(pending,'SQ-VISUAL-002')
        callout=self.create('Authorised call-out — visual test');self.action(self.pm,callout,'review',job_type='callout',urgency='normal',access_responsibility='pm',limit='1500.00')
        deposit_job=self.create('Full job invoice and deposit — visual test');self.action(self.pm,deposit_job,'review',job_type='quoted',urgency='normal',access_responsibility='pm');self.quote(deposit_job,'SQ-VISUAL-FULL',True)
        existing_req=self.create('New repair needing review — visual test',category='Electrical',safety=True)
        self.admin=User.objects.create_user(username='agency-admin-review',first_name='Agency Admin Review',email='agency-admin@example.test')
        Membership.objects.create(user=self.admin,agency=agency,role='admin')
        sessions={}
        for role,user in [('operations',self.ops),('pm',self.pm),('admin',self.admin),('tenant',self.tenant)]:
            c=Client();c.force_login(user);sessions[role]=c.cookies[settings.SESSION_COOKIE_NAME].value
        r=subprocess.run(['node',str(ROOT/'scripts/capture-portal-visual-proof.cjs')],input=json.dumps(dict(url=self.live_server_url,sessions=sessions,job=str(job.pk),pending=str(pending.pk),callout=str(callout.pk),existing_req=str(existing_req.pk),deposit_job=str(deposit_job.pk),pdf=base64.b64encode(document().read()).decode(),report_photo=base64.b64encode((ROOT/'public-site/dist/assets/hero-home.png').read_bytes()).decode(),today=str(timezone.localdate()),output=str(OUTPUT))),text=True,capture_output=True,timeout=300,env=os.environ)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        from portal.account_mail import deliver
        from portal.models import CompletionPackage
        for _ in range(CompletionPackage.objects.count()):deliver(preview=True)
        import shutil
        for index,mail in enumerate((Path(TEMP.name)/'email').glob('*')):shutil.copy2(mail,OUTPUT/('completion-email-preview-'+str(index)+'.eml'))
        print(r.stdout)

if __name__=='__main__':
    from django.test.runner import DiscoverRunner
    try:sys.exit(bool(DiscoverRunner(verbosity=1,interactive=False).run_tests(['__main__.VisualProof'])))
    finally:TEMP.cleanup()
