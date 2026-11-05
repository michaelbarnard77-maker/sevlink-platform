import io
import socket
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.core.files.base import ContentFile
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice
from .models import User, PrivilegedSecurityEvent
from .upload_scanning import scan, ScanUnavailable
from .attachment_storage import PrivateAttachmentStorage

@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False,
                   PRIVILEGED_MFA_REQUIRED=True)
class MFATests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user(username='ops@example.test',email='ops@example.test',password='Long-testing-passphrase-482!',is_staff=True,is_superuser=True)
        self.client.force_login(self.user)

    def test_privileged_pages_and_apis_require_verification(self):
        self.assertRedirects(self.client.get('/maintenance/'),'/security/mfa/',fetch_redirect_response=False)
        self.assertEqual(self.client.get('/api/maintenance/context/').status_code,403)
        self.assertEqual(self.client.get('/security/mfa/').status_code,200)
        self.assertEqual(self.client.post('/logout/').status_code,302)

    def test_password_enrollment_verification_and_token_reuse(self):
        self.client.post('/security/mfa/',{'password':'wrong'})
        self.assertFalse(TOTPDevice.objects.exists())
        self.assertEqual(self.client.post('/security/mfa/',{'password':'Long-testing-passphrase-482!'}).status_code,302)
        device=TOTPDevice.objects.get(); self.assertFalse(device.confirmed)
        self.assertContains(self.client.get('/security/mfa/'),'otpauth://')
        token=str(totp(device.bin_key,step=device.step,t0=device.t0,digits=device.digits)).zfill(6)
        self.assertEqual(self.client.post('/security/mfa/',{'token':token}).status_code,302)
        self.assertEqual(self.client.get('/api/maintenance/context/').status_code,200)
        device.refresh_from_db(); self.assertTrue(device.confirmed)
        self.assertNotContains(self.client.get('/security/mfa/'),'otpauth://')
        self.client.logout(); self.client.force_login(self.user)
        self.assertEqual(self.client.post('/security/mfa/',{'token':token}).status_code,200)
        self.assertEqual(self.client.get('/api/maintenance/context/').status_code,403)
        self.assertEqual(PrivilegedSecurityEvent.objects.count(),2)

    def test_ordinary_user_cannot_enroll_privileged_device(self):
        user=User.objects.create_user(username='ordinary',email='ordinary@example.test')
        self.client.force_login(user)
        self.assertEqual(self.client.get('/security/mfa/').status_code,403)
        self.assertFalse(TOTPDevice.objects.exists())

@override_settings(SECURE_SSL_REDIRECT=False,PORTAL_API_THROTTLING=True,PORTAL_READS_PER_MINUTE=2,PORTAL_WRITES_PER_MINUTE=1,PORTAL_UPLOADS_PER_MINUTE=1)
class ThrottleTests(TestCase):
    def test_limits_are_per_user_and_uploads_have_separate_budget(self):
        user=User.objects.create_user(username='ops',email='ops@example.test',is_superuser=True)
        self.client.force_login(user)
        for _ in range(2): self.assertEqual(self.client.get('/api/maintenance/context/').status_code,200)
        response=self.client.get('/api/maintenance/context/'); self.assertEqual(response.status_code,429)
        self.assertEqual(response['Retry-After'],'60')
        self.assertNotEqual(self.client.post('/api/maintenance/requests/',{}).status_code,429)
        self.assertEqual(self.client.post('/api/maintenance/requests/',{}).status_code,429)
        other=User.objects.create_user(username='other',email='other@example.test',is_superuser=True)
        self.client.force_login(other)
        self.assertEqual(self.client.get('/api/maintenance/context/').status_code,200)

@override_settings(UPLOAD_SCAN_REQUIRED=True,UPLOAD_CLAMAV_SOCKET='/tmp/test-clamav.sock',UPLOAD_SCAN_TIMEOUT=1)
class ScannerTests(TestCase):
    def connection(self,result):
        mock=MagicMock();mock.__enter__.return_value=mock;mock.recv.return_value=result
        return mock

    def test_clean_and_infected_scan_protocol(self):
        clean=self.connection(b'stream: OK\0')
        with patch('portal.upload_scanning.socket.socket',return_value=clean): scan(b'file')
        self.assertEqual(clean.sendall.call_args_list[0].args,(b'zINSTREAM\0',))
        with patch('portal.upload_scanning.socket.socket',return_value=self.connection(b'stream: Eicar-Test-Signature FOUND\0')):
            with self.assertRaises(ScanUnavailable): scan(b'file')

    def test_unavailable_or_incomplete_scanner_fails_closed(self):
        for result in (b'',b'stream: OK',b'ERROR\0'):
            with patch('portal.upload_scanning.socket.socket',return_value=self.connection(result)):
                with self.assertRaises(ScanUnavailable): scan(b'file')
        with patch('portal.upload_scanning.socket.socket',side_effect=OSError):
            with self.assertRaises(ScanUnavailable): scan(b'file')

    def test_storage_never_releases_unscanned_new_or_existing_file(self):
        key='maintenance/11111111-1111-1111-1111-111111111111/22222222-2222-2222-2222-222222222222.pdf'
        with tempfile.TemporaryDirectory() as root:
            storage=PrivateAttachmentStorage(location=root)
            with patch('portal.upload_scanning.scan',side_effect=ScanUnavailable):
                with self.assertRaises(ScanUnavailable): storage.save(key,ContentFile(b'file'))
            self.assertFalse(storage.exists(key))
            with override_settings(UPLOAD_SCAN_REQUIRED=False,AGENCY_REGISTRATION_ENABLED=False): storage.save(key,ContentFile(b'file'))
            with patch('portal.upload_scanning.scan',side_effect=ScanUnavailable):
                with self.assertRaises(ScanUnavailable): storage.open(key)

    def test_deploy_checks_fail_for_disabled_security_controls(self):
        from .checks import launch_security_configuration
        with override_settings(DEBUG=False,PRIVILEGED_MFA_REQUIRED=False,PORTAL_API_THROTTLING=False,UPLOAD_SCAN_REQUIRED=False,AGENCY_REGISTRATION_ENABLED=False):
            self.assertEqual({x.id for x in launch_security_configuration(None)}, {'portal.E010','portal.E011','portal.E012'})


@override_settings(SECURE_SSL_REDIRECT=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False)
class MFARecoveryTests(TestCase):
    def test_recovery_requires_separate_superadmin_and_confirmation(self):
        from django.core.management import call_command, CommandError
        from .models import StaffMFARecovery
        actor=User.objects.create_user(username='recovery',email='recovery@example.test',is_staff=True,is_superuser=True)
        target=User.objects.create_user(username='staff',email='staff@example.test',is_staff=True)
        TOTPDevice.objects.create(user=target,confirmed=True)
        for values in ({'actor':target.pk,'confirmed_identity':True},{'actor':actor.pk,'confirmed_identity':False}):
            with self.assertRaises(CommandError):call_command('reset_staff_mfa',target.pk,reason='Verified synthetic recovery',stdout=io.StringIO(),**values)
        call_command('reset_staff_mfa',target.pk,actor=actor.pk,reason='Verified synthetic recovery',confirmed_identity=True,stdout=io.StringIO())
        self.assertFalse(TOTPDevice.objects.filter(user=target).exists())
        target.refresh_from_db();self.assertEqual(target.session_version,1)
        self.assertEqual(StaffMFARecovery.objects.get().actor,actor)

    def test_staff_offboarding_revokes_sessions_and_cannot_target_self(self):
        from django.core.management import call_command, CommandError
        from django.contrib.auth.models import Permission
        actor=User.objects.create_user(username='staff-owner',email='staff-owner@example.test',is_staff=True,is_superuser=True)
        target=User.objects.create_user(username='departing',email='departing@example.test',is_staff=True)
        target.user_permissions.add(Permission.objects.get(codename='manage_supplier_payments'))
        self.client.force_login(target)
        with self.assertRaises(CommandError):call_command('deactivate_staff',actor.pk,actor=actor.pk,reason_reference='SYNTHETIC-482',confirmed_offboarding=True,stdout=io.StringIO())
        call_command('deactivate_staff',target.pk,actor=actor.pk,reason_reference='SYNTHETIC-482',confirmed_offboarding=True,stdout=io.StringIO())
        target.refresh_from_db();self.assertFalse(target.is_active);self.assertFalse(target.user_permissions.exists())
        self.assertEqual(self.client.get('/api/maintenance/context/').status_code,401)
        self.assertTrue(PrivilegedSecurityEvent.objects.filter(user=target,action__contains='SYNTHETIC-482').exists())
