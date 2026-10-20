import io
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image
from pypdf import PdfWriter

from .attachment_storage import PrivateAttachmentStorage
from .attachments import MAX_BYTES, attachment_data, storage
from .checks import private_upload_directory
from .models import Agency, Audit, MaintenanceAttachment, MaintenanceRequest, Membership, Property, Tenancy, User


def photo(name='photo.png', image_format='PNG', **options):
    stream = io.BytesIO()
    Image.new('RGB', (16, 16), color='blue').save(stream, format=image_format, **options)
    mime = {'PNG': 'image/png', 'JPEG': 'image/jpeg', 'WEBP': 'image/webp'}[image_format]
    return SimpleUploadedFile(name, stream.getvalue(), content_type=mime)


def document(writer=None, name='report.pdf'):
    writer = writer or PdfWriter()
    if not writer.pages:
        writer.add_blank_page(width=100, height=100)
    stream = io.BytesIO()
    writer.write(stream)
    return SimpleUploadedFile(name, stream.getvalue(), content_type='application/pdf')


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False,
                   CSRF_COOKIE_SECURE=False, ALLOWED_HOSTS=['testserver'])
class AttachmentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.agency = Agency.objects.create(name='Attachment Agency A', phone='test', area='Test')
        cls.foreign_agency = Agency.objects.create(name='Attachment Agency B', phone='test', area='Test')
        def user(name, role=None, agency=None, **flags):
            u = User.objects.create_user(username=name+'@example.test', email=name+'@example.test', **flags)
            if role:
                Membership.objects.create(user=u, agency=agency or cls.agency, role=role)
            return u
        cls.tenant = user('photo-tenant', 'tenant')
        cls.pm = user('photo-pm', 'pm')
        cls.admin = user('photo-admin', 'admin')
        cls.other_pm = user('photo-other-pm', 'pm')
        cls.cotenant = user('photo-cotenant', 'tenant')
        cls.foreign = user('photo-foreign', 'pm', cls.foreign_agency)
        cls.staff = user('photo-staff', is_staff=True)
        cls.superadmin = user('photo-superadmin', is_staff=True, is_superuser=True)
        cls.home = Property.objects.create(agency=cls.agency, manager=cls.pm, name='Home A', address='Example address')
        cls.tenancy = Tenancy.objects.create(property=cls.home, user=cls.tenant, name='Tenant', email=cls.tenant.email, phone='test')
        Tenancy.objects.create(property=cls.home, user=cls.cotenant, name='Cotenant', email=cls.cotenant.email, phone='test')
        cls.job = MaintenanceRequest.objects.create(property=cls.home, reported_by=cls.tenant,
            title='Repair', description='Repair description', category='Plumbing')
        cls.upload_url = reverse('maintenance_attachment_upload', args=[cls.job.pk])

    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='sevlink-private-test-')
        self.root = Path(directory.name)
        self.addCleanup(directory.cleanup)
        aliases = {**settings.STORAGES, 'maintenance_private': {
            'BACKEND': 'portal.attachment_storage.PrivateAttachmentStorage', 'OPTIONS': {'location': self.root}}}
        override = override_settings(PRIVATE_ATTACHMENT_ROOT=self.root, STORAGES=aliases)
        override.enable()
        self.addCleanup(override.disable)
        self.client.force_login(self.tenant)

    def upload(self, files=None):
        return self.client.post(self.upload_url, {'attachments': files or [photo()]})

    def stored_files(self):
        return [path for path in self.root.rglob('*') if path.is_file()]

    def uploaded(self):
        response = self.upload()
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()['attachments'][0]

    def test_tenant_can_submit_report_and_photos_in_one_transaction(self):
        response = self.client.post(reverse('maintenance_collection'), {
            'property': str(self.home.pk), 'title': 'Leaking tap', 'description': 'Kitchen leak', 'category': 'Plumbing',
            'attachments': [photo(), photo('second.jpg', 'JPEG')],
        })
        self.assertEqual(response.status_code, 201, response.content)
        job = MaintenanceRequest.objects.get(pk=response.json()['id'])
        self.assertEqual(job.reported_by, self.tenant)
        self.assertEqual(job.attachments.count(), 2)
        self.assertEqual(len(response.json()['attachments']), 2)
        self.assertEqual(len(self.stored_files()), 2)

    def test_authorized_tenant_pm_admin_and_superadmin_can_download(self):
        attachment = self.uploaded()
        for user in [self.tenant, self.pm, self.admin, self.superadmin]:
            self.client.force_login(user)
            response = self.client.get(attachment['download_url'])
            self.assertEqual(response.status_code, 200)
            self.assertTrue(b''.join(response.streaming_content).startswith(b'\x89PNG'))
            self.assertEqual(response['Content-Type'], 'image/png')
            self.assertTrue(response['Content-Disposition'].startswith('attachment;'))
            self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
            self.assertIn('sandbox', response['Content-Security-Policy'])
            self.assertIn('no-store', response['Cache-Control'])
            self.assertEqual(response['Cross-Origin-Resource-Policy'], 'same-origin')
            response.close()

    def test_cross_agency_cotenant_and_unassigned_pm_cannot_access_or_add(self):
        attachment = self.uploaded()
        for user in [self.foreign, self.cotenant, self.other_pm]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(attachment['download_url']).status_code, 404)
            self.assertEqual(self.upload().status_code, 404)
        self.assertEqual(MaintenanceAttachment.objects.count(), 1)
        self.assertEqual(len(self.stored_files()), 1)

    def test_anonymous_inactive_and_plain_staff_are_denied(self):
        attachment = self.uploaded()
        self.client.logout()
        self.assertEqual(self.client.get(attachment['download_url']).status_code, 401)
        self.assertEqual(self.upload().status_code, 401)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(attachment['download_url']).status_code, 403)
        self.assertEqual(self.upload().status_code, 403)
        self.tenant.is_active = False
        self.tenant.save()
        self.client.force_login(self.tenant)
        self.assertEqual(self.client.get(attachment['download_url']).status_code, 401)

    def test_revoked_tenancy_and_reassigned_pm_lose_download_access(self):
        attachment = self.uploaded()
        self.tenancy.active = False
        self.tenancy.save()
        self.assertEqual(self.client.get(attachment['download_url']).status_code, 404)
        self.client.force_login(self.pm)
        self.home.manager = self.other_pm
        self.home.save()
        self.assertEqual(self.client.get(attachment['download_url']).status_code, 404)
        self.client.force_login(self.other_pm)
        response = self.client.get(attachment['download_url'])
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_file_cannot_be_downloaded_through_another_job(self):
        attachment = self.uploaded()
        other_job = MaintenanceRequest.objects.create(property=self.home, reported_by=self.tenant,
            title='Other job', description='Test', category='Plumbing')
        url = reverse('maintenance_attachment_download', args=[other_job.pk, attachment['id']])
        self.client.force_login(self.superadmin)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_pdf_and_webp_are_supported_for_authorized_managers(self):
        self.client.force_login(self.pm)
        response = self.upload([document(), photo('photo.webp', 'WEBP')])
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual({a['content_type'] for a in response.json()['attachments']}, {'application/pdf', 'image/webp'})

    def test_active_encrypted_and_malformed_pdfs_are_rejected(self):
        active = PdfWriter(); active.add_blank_page(width=100, height=100); active.add_js('app.alert("not allowed")')
        encrypted = PdfWriter(); encrypted.add_blank_page(width=100, height=100); encrypted.encrypt('test-fixture-only')
        files = [document(active), document(encrypted),
                 SimpleUploadedFile('bad.pdf', b'%PDF-1.4\nnot a real PDF\n%%EOF', 'application/pdf')]
        for file in files:
            self.assertEqual(self.upload([file]).status_code, 400)
        self.assertEqual(MaintenanceAttachment.objects.count(), 0)
        self.assertEqual(self.stored_files(), [])

    def test_extensions_signatures_and_declared_mime_are_validated(self):
        files = [SimpleUploadedFile('evil.svg', b'<svg onload="alert(1)"></svg>', 'image/svg+xml'),
                 SimpleUploadedFile('evil.html', b'<html>not a photo</html>', 'text/html'),
                 SimpleUploadedFile('fake.png', b'not a photo', 'image/png'),
                 SimpleUploadedFile('fake.jpg', photo().read(), 'image/jpeg'),
                 SimpleUploadedFile('image.png.exe', photo().read(), 'image/png'),
                 SimpleUploadedFile('wrong.png', photo().read(), 'text/html')]
        for file in files:
            self.assertEqual(self.upload([file]).status_code, 400, file.name)
        self.assertEqual(self.stored_files(), [])

    def test_empty_oversized_too_many_and_missing_files_are_rejected(self):
        self.assertEqual(self.upload([SimpleUploadedFile('empty.png', b'', 'image/png')]).status_code, 400)
        self.assertEqual(self.upload([SimpleUploadedFile('big.pdf', b'x'*(MAX_BYTES+1), 'application/pdf')]).status_code, 400)
        self.assertEqual(self.upload([photo(str(i)+'.png') for i in range(6)]).status_code, 400)
        self.assertEqual(self.client.post(self.upload_url, {}).status_code, 400)
        self.assertEqual(self.stored_files(), [])

    def test_maximum_ten_files_is_enforced_and_closed_requests_are_read_only(self):
        for _ in range(2):
            self.assertEqual(self.upload([photo(str(i)+'.png') for i in range(5)]).status_code, 201)
        self.assertEqual(self.upload().status_code, 400)
        self.assertEqual(MaintenanceAttachment.objects.count(), 10)
        MaintenanceRequest.objects.filter(pk=self.job.pk).update(status='completed')
        self.assertEqual(self.upload().status_code, 400)
        response = self.client.get(attachment_data(MaintenanceAttachment.objects.first())['download_url'])
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_uuid_storage_names_prevent_traversal_and_filename_collisions(self):
        self.assertEqual(self.upload([photo('../../secret.png'), photo('C:\\private\\secret.png')]).status_code, 201)
        files = list(MaintenanceAttachment.objects.all())
        self.assertEqual(len({f.storage_key for f in files}), 2)
        for attachment in files:
            self.assertNotIn('secret', attachment.storage_key)
            self.assertNotIn('..', attachment.storage_key)
            self.assertTrue(Path(storage().path(attachment.storage_key)).is_relative_to(self.root))
            self.assertEqual(attachment.filename, 'secret.png')
        if os.name != 'nt':
            self.assertEqual(self.stored_files()[0].stat().st_mode & 0o777, 0o600)

    def test_private_storage_rejects_paths_urls_and_public_directory_settings(self):
        backend = storage()
        for key in ['../../escape.png', '/etc/passwd', 'maintenance/../escape.pdf', 'https://example.test/file.png']:
            with self.assertRaises(SuspiciousFileOperation):
                backend.path(key)
        with self.assertRaises(NotImplementedError):
            backend.url('anything')
        with self.settings(PRIVATE_ATTACHMENT_ROOT=settings.STATIC_ROOT / 'private'):
            self.assertEqual(private_upload_directory(None)[0].id, 'portal.E001')
        self.assertEqual(private_upload_directory(None), [])

    def test_symlink_escape_is_rejected_and_existing_objects_are_not_overwritten(self):
        info = self.uploaded()
        attachment = MaintenanceAttachment.objects.get(pk=info['id'])
        with self.assertRaises(FileExistsError):
            storage().save(attachment.storage_key, ContentFile(b'replacement'))
        outside = self.root / 'outside'
        outside.mkdir()
        link_root = self.root / 'storage'
        link_root.mkdir()
        (link_root / 'maintenance').symlink_to(outside, target_is_directory=True)
        backend = PrivateAttachmentStorage(location=link_root)
        with self.assertRaises(SuspiciousFileOperation):
            backend.path(attachment.storage_key)

    def test_photos_are_reencoded_and_metadata_and_appended_payload_removed(self):
        exif = Image.Exif(); exif[315] = 'PRIVATE CAMERA OWNER'
        upload = photo('private.jpg', 'JPEG', exif=exif)
        upload = SimpleUploadedFile(upload.name, upload.read()+b'<script>appended payload</script>', 'image/jpeg')
        self.assertEqual(self.upload([upload]).status_code, 201)
        data = self.stored_files()[0].read_bytes()
        self.assertNotIn(b'PRIVATE CAMERA OWNER', data)
        self.assertNotIn(b'<script>', data)
        with Image.open(io.BytesIO(data)) as image:
            self.assertFalse(image.getexif())
            self.assertEqual(image.size, (16, 16))

    def test_pixel_limit_truncation_and_animated_images_are_rejected(self):
        with patch('portal.attachments.MAX_PIXELS', 100):
            self.assertEqual(self.upload().status_code, 400)
        truncated = SimpleUploadedFile('truncated.png', photo().read()[:40], 'image/png')
        self.assertEqual(self.upload([truncated]).status_code, 400)
        output = io.BytesIO()
        Image.new('RGB', (8, 8), 'red').save(output, format='PNG', save_all=True,
            append_images=[Image.new('RGB', (8, 8), 'blue')], duration=100, loop=0)
        self.assertEqual(self.upload([SimpleUploadedFile('animated.png', output.getvalue(), 'image/png')]).status_code, 400)

    def test_mixed_invalid_batch_does_not_save_report_or_any_files(self):
        response = self.client.post(reverse('maintenance_collection'), {
            'property': str(self.home.pk), 'title': 'New repair', 'description': 'Test', 'category': 'Plumbing',
            'attachments': [photo(), SimpleUploadedFile('bad.pdf', b'bad', 'application/pdf')]})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(MaintenanceRequest.objects.count(), 1)
        self.assertEqual(MaintenanceAttachment.objects.count(), 0)
        self.assertEqual(self.stored_files(), [])

    def test_storage_failure_rolls_back_report_and_cleans_saved_files(self):
        backend = storage()
        original_save = backend.save
        count = 0
        def fail_second(*args, **kwargs):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError('storage test failure')
            return original_save(*args, **kwargs)
        with patch.object(backend, 'save', side_effect=fail_second):
            response = self.client.post(reverse('maintenance_collection'), {
                'property': str(self.home.pk), 'title': 'New repair', 'description': 'Test', 'category': 'Plumbing',
                'attachments': [photo(), photo('second.png')]})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(MaintenanceRequest.objects.count(), 1)
        self.assertEqual(MaintenanceAttachment.objects.count(), 0)
        self.assertEqual(self.stored_files(), [])

    def test_database_failure_cleans_files_and_missing_download_does_not_leak_key(self):
        with patch('portal.attachments.Audit.objects.create', side_effect=RuntimeError('test rollback')):
            with self.assertRaises(RuntimeError):
                self.upload()
        self.assertEqual(self.stored_files(), [])
        self.assertEqual(MaintenanceAttachment.objects.count(), 0)
        info = self.uploaded()
        attachment = MaintenanceAttachment.objects.get(pk=info['id'])
        storage().delete(attachment.storage_key)
        response = self.client.get(info['download_url'])
        self.assertEqual(response.status_code, 404)
        # Production 404 has no local paths or object keys.
        with self.settings(DEBUG=False):
            response = self.client.get(info['download_url'])
            self.assertNotIn(attachment.storage_key, response.content.decode())

    def test_metadata_never_contains_private_storage_key_or_uploader(self):
        self.uploaded()
        record = MaintenanceAttachment.objects.get()
        response = self.client.get(reverse('maintenance_detail', args=[self.job.pk])).json()
        item = response['attachments'][0]
        self.assertEqual(set(item), {'id', 'filename', 'content_type', 'size', 'created_at', 'download_url'})
        self.assertNotIn(record.storage_key, str(response))
        self.assertNotIn('uploaded_by', str(response))
        self.assertIsNone(finders.find(record.storage_key))
        self.assertEqual(self.client.get('/media/'+record.storage_key).status_code, 404)

    def test_csrf_and_methods_are_enforced(self):
        info = self.uploaded()
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.tenant)
        self.assertEqual(strict.post(self.upload_url, {'attachments': photo()}).status_code, 403)
        strict.get(reverse('maintenance_context'))
        token = strict.cookies['csrftoken'].value
        self.assertEqual(strict.post(self.upload_url, {'attachments': photo()}, HTTP_X_CSRFTOKEN=token).status_code, 201)
        self.assertEqual(self.client.get(self.upload_url).status_code, 405)
        self.assertEqual(self.client.post(info['download_url']).status_code, 405)

    def test_spoofed_upload_fields_and_foreign_property_reports_are_rejected(self):
        response = self.client.post(self.upload_url, {'storage_key': '../../escape', 'attachments': photo()})
        self.assertEqual(response.status_code, 400)
        self.client.force_login(self.foreign)
        self.assertEqual(self.upload().status_code, 404)
        self.assertEqual(MaintenanceAttachment.objects.count(), 0)

    def test_orientation_is_applied_before_stripping_exif(self):
        exif = Image.Exif(); exif[274] = 6
        stream = io.BytesIO()
        Image.new('RGB', (16, 8), 'blue').save(stream, format='JPEG', exif=exif)
        file = SimpleUploadedFile('rotated.jpg', stream.getvalue(), 'image/jpeg')
        self.assertEqual(self.upload([file]).status_code, 201)
        with Image.open(self.stored_files()[0]) as image:
            self.assertEqual(image.size, (8, 16))
            self.assertFalse(image.getexif())

    def test_partial_local_write_is_removed_and_download_errors_are_generic(self):
        info = self.uploaded()
        key = f'maintenance/{self.job.pk}/00000000-0000-0000-0000-000000000000.png'
        class BrokenContent(ContentFile):
            def chunks(self, chunk_size=None):
                yield b'partial'
                raise OSError('test write failure')
        with self.assertRaises(OSError):
            storage().save(key, BrokenContent(b'test'))
        self.assertFalse(storage().exists(key))
        with patch.object(storage(), 'open', side_effect=OSError('private path or credentials')):
            response = self.client.get(info['download_url'])
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('credentials', response.content.decode())
