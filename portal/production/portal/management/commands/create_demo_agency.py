"""Create an isolated, clearly labelled agency/PM/tenant presentation dataset."""
import getpass
from django.core.management.base import BaseCommand,CommandError
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from portal.models import User,Agency,Membership,Property,Tenancy,AccountLifecycleEvent,Audit

ROLE_DATA=[('admin',Membership.ADMIN,'Demo Agency','Admin'),('pm',Membership.PM,'Alex','Morgan'),('tenant',Membership.TENANT,'Jordan','Taylor')]
AGENCY='Sevlink Demo Agency'
ADDRESS='24 Example Lane, Pretoria East (fictional demo address)'

class Command(BaseCommand):
    help='Prepare isolated demo agency roles and one fictional property. No invitations or email are sent; passwords are entered privately.'

    def add_arguments(self,parser):
        parser.add_argument('--actor',required=True,help='Existing Sevlink superuser email for the audit trail.')
        parser.add_argument('--inbox',required=True,help='Your controlled email inbox; plus-addressed demo aliases are created.')
        parser.add_argument('--apply',action='store_true',help='Create the demo records; otherwise preview only.')
        parser.add_argument('--reset-passwords',action='store_true',help='Explicitly reset passwords for these demo accounts only.')

    def emails(self,inbox):
        try:validate_email(inbox)
        except ValidationError:raise CommandError('Enter a valid inbox you control.') from None
        local,domain=inbox.strip().lower().split('@')
        local=local.split('+',1)[0]
        aliases={role:f'{local}+sevlink-demo-{role}@{domain}' for role,*_ in ROLE_DATA}
        for email in aliases.values():
            try:validate_email(email)
            except ValidationError:raise CommandError('The generated demo alias is too long.') from None
        return aliases

    def inspect(self,emails):
        agencies=Agency.objects.filter(name__iexact=AGENCY)
        if agencies.count()>1:raise CommandError('Multiple matching demo agencies exist; no changes made.')
        agency=agencies.first()
        if agency and (agency.kind!='agency' or not AccountLifecycleEvent.objects.filter(agency=agency,action='demo_agency_setup').exists()):
            raise CommandError('An existing agency uses this name without the demo setup marker; no changes made.')
        users={}
        for role,membership,*_ in ROLE_DATA:
            user=User.objects.filter(email__iexact=emails[role]).first()
            if user:
                member=Membership.objects.filter(user=user).first()
                if user.is_staff or user.is_superuser or user.username!=emails[role] or not agency or not member or member.agency_id!=agency.pk or member.role!=membership:
                    raise CommandError('A demo email is already used by an unrelated or privileged account; no changes made.')
            users[role]=user
        return agency,users

    def handle(self,*args,**options):
        actor=User.objects.filter(email__iexact=options['actor'],is_superuser=True,is_active=True).first()
        if not actor:raise CommandError('An existing active Sevlink superuser is required.')
        emails=self.emails(options['inbox']);agency,users=self.inspect(emails)
        if not options['apply']:
            self.stdout.write('PREVIEW ONLY — no records changed')
            self.output(emails)
            return
        ready=agency and all(users.values())
        if ready and not options['reset_passwords']:
            if not all(user.is_active for user in users.values()):raise CommandError('An existing demo account is disabled. Use --reset-passwords explicitly to reactivate the demo accounts.')
            self.stdout.write('Existing demo accounts retained; passwords unchanged.')
            self.output(emails)
            return
        password=getpass.getpass('Choose a strong password for the three demo roles (hidden): ')
        confirmation=getpass.getpass('Confirm demo password (hidden): ')
        if password!=confirmation:raise CommandError('Passwords did not match; no changes made.')
        for role,*_ in ROLE_DATA:
            try:validate_password(password,user=users[role] or User(username=emails[role],email=emails[role]))
            except ValidationError as error:raise CommandError(' '.join(error.messages)) from None
        with transaction.atomic():
            User.objects.select_for_update().get(pk=actor.pk)
            agency,users=self.inspect(emails)
            if not agency:agency=Agency.objects.create(name=AGENCY,kind='agency',phone='Demo only — no live number',area='Gauteng and Cape Town')
            for role,membership,first,last in ROLE_DATA:
                user=users[role]
                if not user:
                    user=User.objects.create_user(username=emails[role],email=emails[role],password=password,first_name=first,last_name=last,is_active=True,is_staff=False,is_superuser=False)
                    Membership.objects.create(user=user,agency=agency,role=membership)
                    users[role]=user
                elif options['reset_passwords']:
                    user.set_password(password);user.is_active=True;user.session_version+=1
                    user.save(update_fields=['password','is_active','session_version'])
            prop,created=Property.objects.get_or_create(agency=agency,address=ADDRESS,defaults={'name':'Demo Property — Pretoria East','manager':users['pm'],'access_responsibility':'sevlink','access_notes':'Demonstration only. No real tenant, keys or access codes.'})
            if prop.manager_id!=users['pm'].pk:raise CommandError('The existing demo property has another manager; no changes made.')
            tenancy,created=Tenancy.objects.get_or_create(property=prop,email=emails['tenant'],active=True,defaults={'user':users['tenant'],'name':'Jordan Taylor — Demo Tenant','phone':'Demo only — no live number'})
            if tenancy.user_id!=users['tenant'].pk:raise CommandError('The existing demo tenancy belongs to another user; no changes made.')
            AccountLifecycleEvent.objects.create(agency=agency,actor=actor,action='demo_agency_setup',object_reference=str(prop.pk),reason='Owner-authorised fictional presentation accounts. No jobs, invoices or emails created.')
            Audit.objects.create(agency=agency,actor=actor,action='Demo agency roles and property prepared',object_id=str(prop.pk))
        self.stdout.write(self.style.SUCCESS('DEMO AGENCY READY — passwords not displayed; no emails sent'))
        self.output(emails)

    def output(self,emails):
        self.stdout.write('Agency: '+AGENCY)
        for role in ('admin','pm','tenant'):self.stdout.write(role.upper()+': '+emails[role])
        self.stdout.write('Property: '+ADDRESS)
        self.stdout.write('All three accounts are non-staff, scoped to this fictional demo agency.')
