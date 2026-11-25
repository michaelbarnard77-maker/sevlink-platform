"""Explicitly isolated, loopback-only Windows/local design preview settings."""
import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
if os.environ.get('SEVLINK_LOCAL_PREVIEW')!='1':
    raise ImproperlyConfigured('Use Preview-Redesign.cmd to start the isolated local preview.')
from .settings import *  # noqa: F403
if not DEBUG:
    raise ImproperlyConfigured('The redesign preview requires DEBUG=1.')
preview_path=Path(os.environ['SEVLINK_PREVIEW_ROOT']).resolve()
REDESIGN_PREVIEW=True
DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':preview_path/'redesign.sqlite3'}}
ALLOWED_HOSTS=['127.0.0.1','localhost','testserver']
SITE_URL='http://127.0.0.1:8000'
SMTP_DELIVERY_ENABLED=False
OPERATIONS_LIVE_DELIVERY_ENABLED=False
EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
OPERATIONS_EMAIL_DELIVERY_BACKEND='django.core.mail.backends.locmem.EmailBackend'
PRIVILEGED_MFA_REQUIRED=False
UPLOAD_SCAN_REQUIRED=False
PRIVATE_ATTACHMENT_ROOT=preview_path/'private-attachments'
STORAGES={**STORAGES,'maintenance_private':{'BACKEND':'portal.attachment_storage.PrivateAttachmentStorage','OPTIONS':{'location':PRIVATE_ATTACHMENT_ROOT}}}
EMAIL_FILE_PATH=preview_path/'private-email-preview'
