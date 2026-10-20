from pathlib import Path

from django.conf import settings
from django.core.checks import Error, register


@register()
def private_upload_directory(app_configs, **kwargs):
    root = Path(settings.PRIVATE_ATTACHMENT_ROOT).resolve()
    public = [settings.STATIC_ROOT, settings.PORTAL_UI_DIR, settings.BASE_DIR.parent.parent / 'public-site' / 'dist']
    if settings.MEDIA_ROOT:
        public.append(settings.MEDIA_ROOT)
    for directory in settings.STATICFILES_DIRS:
        public.append(directory[1] if isinstance(directory, (tuple, list)) else directory)
    for directory in public:
        if directory and (root.is_relative_to(Path(directory).resolve()) or Path(directory).resolve().is_relative_to(root)):
            return [Error('Private attachment storage must be outside publicly served directories.', id='portal.E001')]
    return []
