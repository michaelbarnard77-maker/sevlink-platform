from pathlib import Path

from django.conf import settings
from django.core.checks import Error, register
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from urllib.parse import urlsplit


@register()
def private_upload_directory(app_configs, **kwargs):
    roots = [Path(settings.PRIVATE_ATTACHMENT_ROOT).resolve(), Path(settings.EMAIL_FILE_PATH).resolve()]
    public = [settings.STATIC_ROOT, settings.PORTAL_UI_DIR, settings.BASE_DIR.parent.parent / 'public-site' / 'dist']
    if settings.MEDIA_ROOT:
        public.append(settings.MEDIA_ROOT)
    for directory in settings.STATICFILES_DIRS:
        public.append(directory[1] if isinstance(directory, (tuple, list)) else directory)
    for root in roots:
        for directory in public:
            if directory and (root.is_relative_to(Path(directory).resolve()) or Path(directory).resolve().is_relative_to(root)):
                return [Error('Private files/previews must be outside publicly served directories.', id='portal.E001')]
    return []


@register()
def operations_configuration(app_configs, **kwargs):
    errors = []
    try:
        validate_email(settings.OPERATIONS_NOTIFICATION_EMAIL)
    except ValidationError:
        errors.append(Error('Set one valid Operations notification email address.', id='portal.E002'))
    site = urlsplit(settings.SITE_URL)
    if site.scheme not in ('http', 'https') or not site.hostname or site.username or site.password or site.query or site.fragment:
        errors.append(Error('SITE_URL must be a trusted origin without credentials, query or fragment.', id='portal.E003'))
    return errors


@register()
def live_email_configuration(app_configs, **kwargs):
    if not settings.OPERATIONS_LIVE_DELIVERY_ENABLED:
        return []
    if settings.OPERATIONS_EMAIL_DELIVERY_BACKEND == 'django.core.mail.backends.smtp.EmailBackend':
        if not settings.EMAIL_HOST or not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD or settings.EMAIL_USE_TLS == settings.EMAIL_USE_SSL:
            return [Error('Live SMTP requires host/secret credentials and exactly one TLS mode.', id='portal.E004')]
    return []


@register(deploy=True)
def launch_security_configuration(app_configs, **kwargs):
    if settings.DEBUG:
        return []
    errors = []
    for enabled, message, identifier in [
        (settings.PRIVILEGED_MFA_REQUIRED, 'Production requires privileged MFA.', 'portal.E010'),
        (settings.PORTAL_API_THROTTLING, 'Production requires API throttling.', 'portal.E011'),
        (settings.UPLOAD_SCAN_REQUIRED, 'Production requires private upload scanning.', 'portal.E012'),
    ]:
        if not enabled:
            errors.append(Error(message, id=identifier))
    if settings.UPLOAD_SCAN_REQUIRED and not Path(settings.UPLOAD_CLAMAV_SOCKET).is_absolute():
        errors.append(Error('Configure a private absolute ClamAV socket path.', id='portal.E013'))
    if settings.AGENCY_REGISTRATION_ENABLED and not settings.AGENCY_REGISTRATION_ALLOWED_EMAILS:
        errors.append(Error('Controlled launch registration requires an explicit approved-email list.', id='portal.E014'))
    return errors
