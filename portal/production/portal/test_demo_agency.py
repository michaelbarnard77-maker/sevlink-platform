import io
import secrets
from unittest.mock import patch
from django.core.management import call_command,CommandError
from django.test import TestCase
from .models import User,Agency,Membership,Property,Tenancy,MaintenanceRequest,JobInvoice,MailQueue,OperationsNotification

class DemoAgencyTests(TestCase):
    def setUp(self):
        self.actor=User.objects.create_superuser(username='owner@example.test',email='owner@example.test',password=secrets.token_urlsafe(24))
        self.password=secrets.token_urlsafe(24)

    def run_setup(self,**options):
        with patch('getpass.getpass',side_effect=[self.password,self.password]):
            call_command('create_demo_agency',actor=self.actor.email,inbox='owner@example.test',stdout=io.StringIO(),**options)

    def test_creates_only_isolated_non_staff_roles_and_linked_property(self):
        from .maintenance import properties_for
        real=Agency.objects.create(name='Unrelated real agency')
        Property.objects.create(agency=real,name='Unrelated property',address='Not part of the demonstration')
        self.run_setup(apply=True)
        agency=Agency.objects.get(name='Sevlink Demo Agency')
        roles={m.role:m.user for m in Membership.objects.filter(agency=agency)}
        self.assertEqual(set(roles),{'admin','pm','tenant'})
        for user in roles.values():
            self.assertFalse(user.is_staff);self.assertFalse(user.is_superuser);self.assertTrue(user.is_active);self.assertTrue(user.check_password(self.password))
        prop=Property.objects.get(agency=agency);self.assertEqual(prop.manager,roles['pm'])
        for user in roles.values():self.assertEqual(set(properties_for(user).values_list('pk',flat=True)),{prop.pk})
        self.assertEqual(Tenancy.objects.get(property=prop).user,roles['tenant'])
        for model in (MaintenanceRequest,JobInvoice,MailQueue,OperationsNotification):self.assertEqual(model.objects.count(),0)

    def test_preview_does_not_create_any_records(self):
        self.run_setup()
        self.assertEqual(User.objects.count(),1);self.assertFalse(Agency.objects.exists())

    def test_repeat_preserves_passwords_and_does_not_duplicate_records(self):
        self.run_setup(apply=True)
        with patch('getpass.getpass',side_effect=AssertionError('Do not prompt for a repeat without reset')):
            call_command('create_demo_agency',actor=self.actor.email,inbox='owner@example.test',apply=True,stdout=io.StringIO())
        self.assertEqual(User.objects.count(),4);self.assertEqual(Property.objects.count(),1);self.assertEqual(Tenancy.objects.count(),1)

    def test_does_not_take_over_existing_email_or_existing_agency(self):
        User.objects.create_user(username='existing',email='owner+sevlink-demo-pm@example.test')
        with self.assertRaises(CommandError):self.run_setup(apply=True)
        self.assertFalse(Agency.objects.exists())

    def test_reset_is_explicit_and_does_not_change_real_owner(self):
        self.run_setup(apply=True);old=self.actor.password
        self.password=secrets.token_urlsafe(24);self.run_setup(apply=True,reset_passwords=True)
        for user in User.objects.exclude(pk=self.actor.pk):self.assertTrue(user.check_password(self.password))
        self.actor.refresh_from_db();self.assertEqual(self.actor.password,old)
