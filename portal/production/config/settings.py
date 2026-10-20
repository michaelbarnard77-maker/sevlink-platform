import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get('DEBUG') == '1'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    raise ImproperlyConfigured('Set DJANGO_SECRET_KEY before starting Sevlink.')
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
SITE_URL = os.environ.get('SITE_URL', 'http://localhost:8000').rstrip('/')
if not DEBUG and ('REPLACE_' in SECRET_KEY or 'REPLACE_' in os.environ.get('DB_PASSWORD','')):
    raise ImproperlyConfigured('Replace deployment secret placeholders before starting.')
if not DEBUG and (not SITE_URL.startswith('https://') or not os.environ.get('DB_HOST')):
    raise ImproperlyConfigured('Production requires an HTTPS SITE_URL and PostgreSQL DB_HOST.')
INSTALLED_APPS = ['django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','portal']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
AUTH_USER_MODEL = 'portal.User'
AUTH_PASSWORD_VALIDATORS = [{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS':{'min_length':12}},{'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},{'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
if os.environ.get('DB_HOST'):
    DATABASES = {'default':{'ENGINE':'django.db.backends.postgresql','NAME':os.environ.get('DB_NAME','sevlink'),'USER':os.environ.get('DB_USER','sevlink'),'PASSWORD':os.environ.get('DB_PASSWORD',''),'HOST':os.environ['DB_HOST'],'PORT':os.environ.get('DB_PORT','5432'),'CONN_MAX_AGE':60}}
else:
    DATABASES = {'default':{'ENGINE':'django.db.backends.sqlite3','NAME':BASE_DIR/'development.sqlite3'}}
EMAIL_BACKEND = 'portal.mail.QueueBackend'
SMTP_DELIVERY_ENABLED = os.environ.get('SMTP_DELIVERY_ENABLED') == '1'
SECURE_REFERRER_POLICY = 'no-referrer'
EMAIL_HOST = os.environ.get('EMAIL_HOST','')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT','587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER','')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD','')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS','1')=='1'
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL','0')=='1'
EMAIL_TIMEOUT = 15
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL','Sevlink <noreply@sevlink.co.za>')
LANGUAGE_CODE = 'en-za'
TIME_ZONE = 'Africa/Johannesburg'
USE_TZ = True
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR/'collected-static'
STATICFILES_DIRS = [BASE_DIR/'static']
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 8*60*60
CSRF_COOKIE_SECURE = not DEBUG
CSRF_TRUSTED_ORIGINS = [SITE_URL] if SITE_URL.startswith('https://') else []
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
# Only the private reverse proxy may reach Gunicorn; it overwrites this header.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO','https')

PASSWORD_RESET_TIMEOUT = 3600

# Source checkout and container layouts both retain the original portal assets.
PORTAL_UI_DIR = BASE_DIR / 'frontend' if (BASE_DIR / 'frontend').exists() else BASE_DIR.parent / 'dist'
STATICFILES_DIRS += [('maintenance-ui', PORTAL_UI_DIR)]

# Never add this directory to STATICFILES_DIRS, MEDIA_URL, or a public web server.
PRIVATE_ATTACHMENT_ROOT = Path(os.environ.get('PRIVATE_ATTACHMENT_ROOT', BASE_DIR / 'private-attachments'))
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    'maintenance_private': {'BACKEND': 'portal.attachment_storage.PrivateAttachmentStorage'},
}
FILE_UPLOAD_HANDLERS = [
    'portal.attachments.BoundedUploadHandler',
    'django.core.files.uploadhandler.MemoryFileUploadHandler',
    'django.core.files.uploadhandler.TemporaryFileUploadHandler',
]
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 65536
DATA_UPLOAD_MAX_NUMBER_FILES = 5
DATA_UPLOAD_MAX_NUMBER_FIELDS = 20

# Domain events are always queued. Delivery is local-only unless explicitly enabled.
OPERATIONS_NOTIFICATION_EMAIL = os.environ.get('OPERATIONS_NOTIFICATION_EMAIL', 'maintenance@sevlink.co.za')
OPERATIONS_EMAIL_DELIVERY_BACKEND = os.environ.get('OPERATIONS_EMAIL_DELIVERY_BACKEND', 'portal.mail.PrivatePreviewBackend')
OPERATIONS_LIVE_DELIVERY_ENABLED = os.environ.get('OPERATIONS_LIVE_DELIVERY_ENABLED') == '1'
EMAIL_FILE_PATH = BASE_DIR / 'private-email-preview'
