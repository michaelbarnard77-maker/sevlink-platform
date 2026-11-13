"""Private local backend. Views use Django's named Storage API, never public URLs."""
import os
import re
from pathlib import Path

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import FileSystemStorage

KEY = re.compile(r'(?:maintenance/[0-9a-f-]{36}/[0-9a-f-]{36}\.(?:jpg|png|webp|pdf)|subcontractors/[0-9a-f-]{36}/[0-9a-f-]{36}\.pdf)\Z')


class PrivateAttachmentStorage(FileSystemStorage):
    def __init__(self, **kwargs):
        kwargs.setdefault('location', settings.PRIVATE_ATTACHMENT_ROOT)
        kwargs.setdefault('file_permissions_mode', 0o600)
        kwargs.setdefault('directory_permissions_mode', 0o700)
        super().__init__(**kwargs)

    def path(self, name):
        if not KEY.fullmatch(str(name)):
            raise SuspiciousFileOperation('Invalid private attachment key.')
        path = super().path(name)
        if not Path(path).resolve().is_relative_to(Path(self.location).resolve()):
            raise SuspiciousFileOperation('Private attachment path escapes storage.')
        return path

    def url(self, name):
        raise NotImplementedError('Private attachments have no public storage URLs.')

    def get_available_name(self, name, max_length=None):
        self.path(name)
        if self.exists(name):
            raise FileExistsError('Attachment key already exists.')
        return name

    def _open(self, name, mode='rb'):
        if settings.UPLOAD_SCAN_REQUIRED:
            from .upload_scanning import scan
            from django.core.files.base import ContentFile
            with super()._open(name, mode) as source:
                data = source.read(5 * 1024 * 1024 + 1)
            scan(data)
            return ContentFile(data, name=name)
        return super()._open(name, mode)

    def _save(self, name, content):
        if settings.UPLOAD_SCAN_REQUIRED:
            from .upload_scanning import scan
            from django.core.files.base import ContentFile
            data = content.read(5 * 1024 * 1024 + 1)
            scan(data)
            content = ContentFile(data)
        path = Path(self.path(name))
        # All names are server-generated UUIDs; never use a browser filename as a path.
        root = Path(self.location)
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        created = False
        try:
            # O_EXCL prevents collision overwrite; restrict permissions at creation.
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            created = True
            with os.fdopen(descriptor, 'wb') as destination:
                for chunk in content.chunks():
                    destination.write(chunk)
        except Exception:
            if created:
                path.unlink(missing_ok=True)
            raise
        return name
