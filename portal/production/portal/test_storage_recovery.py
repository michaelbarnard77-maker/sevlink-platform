import hashlib
import io
import shutil
import tempfile
from pathlib import Path
from django.test import TestCase, override_settings
from django.conf import settings
from django.core.management import call_command, CommandError
from django.core.files.base import ContentFile
from .models import Agency, User, Property, MaintenanceRequest, MaintenanceAttachment
from .attachment_storage import PrivateAttachmentStorage

class StorageRecoveryTests(TestCase):
    def test_restored_file_hashes_match_and_missing_or_corrupt_files_fail(self):
        key='maintenance/11111111-1111-1111-1111-111111111111/22222222-2222-2222-2222-222222222222.pdf'
        data=b'Synthetic private recovery fixture'
        agency=Agency.objects.create(name='Synthetic restore agency')
        user=User.objects.create_user(username='restore',email='restore@example.test')
        home=Property.objects.create(agency=agency,name='Synthetic',address='Synthetic')
        job=MaintenanceRequest.objects.create(property=home,reported_by=user,title='Synthetic',description='Synthetic',category='Plumbing')
        MaintenanceAttachment.objects.create(request=job,uploaded_by=user,storage_key=key,filename='synthetic.pdf',content_type='application/pdf',size=len(data),sha256=hashlib.sha256(data).hexdigest())
        with tempfile.TemporaryDirectory() as root:
            original=Path(root)/'original';restored=Path(root)/'restored'
            PrivateAttachmentStorage(location=original).save(key,ContentFile(data))
            shutil.copytree(original,restored)
            aliases={**settings.STORAGES,'maintenance_private':{
                'BACKEND':'portal.attachment_storage.PrivateAttachmentStorage','OPTIONS':{'location':str(restored)}}}
            with override_settings(STORAGES=aliases):
                call_command('verify_private_files',stdout=io.StringIO())
                (restored/key).write_bytes(b'corrupt')
                with self.assertRaises(CommandError):call_command('verify_private_files',stdout=io.StringIO())
                (restored/key).unlink()
                with self.assertRaises(CommandError):call_command('verify_private_files',stdout=io.StringIO())
