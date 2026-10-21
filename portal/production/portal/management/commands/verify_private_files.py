"""Read-only integrity verification for a restored private database/file pair."""
import hashlib
from django.core.management.base import BaseCommand, CommandError
from portal.attachments import storage
from portal.models import MaintenanceAttachment, ComplianceDocument


class Command(BaseCommand):
    help='Verify restored private files against saved sizes and SHA-256 hashes; no names or personal data are printed.'

    def handle(self,*args,**options):
        checked=failed=0
        for model in (MaintenanceAttachment,ComplianceDocument):
            for item in model.objects.all().iterator():
                checked+=1
                digest=hashlib.sha256();size=0
                try:
                    with storage().open(item.storage_key,'rb') as source:
                        while True:
                            chunk=source.read(65536)
                            if not chunk:break
                            size+=len(chunk);digest.update(chunk)
                    if size!=item.size or digest.hexdigest()!=item.sha256:failed+=1
                except (OSError,ValueError):failed+=1
        self.stdout.write(f'Private file verification: {checked} checked; {failed} failed.')
        if failed:raise CommandError('Restored files are missing, changed or unavailable. Do not release this environment.')
