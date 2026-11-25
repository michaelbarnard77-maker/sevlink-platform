"""Seed synthetic review accounts only in the explicitly isolated local preview database."""
from getpass import getpass
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from portal.models import User,Agency,Membership,Property,Tenancy,MaintenanceRequest,MaintenanceStatusEvent

ACCOUNTS=[('superadmin@sevlink.example','Sevlink Preview','superadmin'),('admin@sevlink.example','Demo Agency Admin','admin'),('pm@sevlink.example','Alex Morgan','pm'),('tenant@sevlink.example','Jordan Taylor','tenant')]

class Command(BaseCommand):
    help='Create four synthetic role accounts in the isolated local redesign preview, never a live database.'
    def handle(self,*args,**options):
        if not getattr(settings,'REDESIGN_PREVIEW',False) or not settings.DEBUG or settings.DATABASES['default']['ENGINE']!='django.db.backends.sqlite3' or str(settings.DATABASES['default']['NAME']).split('/')[-1].split('\\')[-1]!='redesign.sqlite3':
            raise CommandError('Refusing: this command only runs with config.redesign_preview and its isolated database.')
        if User.objects.exists():
            self.stdout.write('Existing preview accounts and records retained. No passwords changed.')
        else:
            password=getpass('Choose a password for the four LOCAL PREVIEW accounts (hidden): ')
            if password!=getpass('Confirm preview password: '):raise CommandError('Passwords did not match. Nothing created.')
            try:validate_password(password)
            except ValidationError as e:raise CommandError('; '.join(e.messages))
            with transaction.atomic():
                users={}
                agency=Agency.objects.create(name='Sevlink Preview Agency',phone='000 000 0000',area='Fictional preview portfolio')
                for email,name,role in ACCOUNTS:
                    user=User.objects.create_user(username=email,email=email,first_name=name,password=password,is_staff=role=='superadmin',is_superuser=role=='superadmin');users[role]=user
                    if role!='superadmin':Membership.objects.create(user=user,agency=agency,role=role)
                prop=Property.objects.create(agency=agency,manager=users['pm'],name='Fictional preview property',address='24 Example Lane, Pretoria East')
                Property.objects.create(agency=agency,manager=users['admin'],name='Fictional admin property',address='8 Example Avenue, Centurion')
                Tenancy.objects.create(property=prop,user=users['tenant'],name='Jordan Taylor',email=users['tenant'].email,phone='000 000 0000')
                job=MaintenanceRequest.objects.create(property=prop,reported_by=users['tenant'],title='Kitchen tap leaking',description='Fictional preview repair. Water collects at the base of the kitchen tap.',category='Plumbing',workflow_version=1,jobs_payment_route='pending',access_information='Fictional access note: please call before attending.',internal_notes='Preview handover note. This text is visible only to authorised Sevlink staff.')
                MaintenanceStatusEvent.objects.create(request=job,actor=users['tenant'],status=job.status)
                # A second agency is intentional: reviewers can check portfolio isolation.
                foreign=Agency.objects.create(name='Separate Preview Agency',phone='000 000 0000',area='Fictional isolation check')
                other=Property.objects.create(agency=foreign,name='Not in the demo agency portfolio',address='99 Isolation Example Road')
                MaintenanceRequest.objects.create(property=other,reported_by=users['superadmin'],title='Separate agency isolation check',description='Must not appear for the demo agency admin, PM or tenant.',category='Electrical')
            self.stdout.write(self.style.SUCCESS('LOCAL PREVIEW READY. Fictional accounts only. No emails sent.'))
        for email,_,role in ACCOUNTS:self.stdout.write(role.upper()+': '+email)
        self.stdout.write('Sign in at http://127.0.0.1:8000/login/ using the preview password you chose.')
