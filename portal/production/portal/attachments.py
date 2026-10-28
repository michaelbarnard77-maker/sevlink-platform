"""Bounded uploads, decoded/re-encoded photos, conservative PDF validation and private delivery."""
import hashlib
import io
import logging
import uuid
import warnings
from pathlib import Path

from django.conf import settings
from django.core.exceptions import RequestDataTooBig, TooManyFilesSent, TooManyFieldsSent
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.core.files.uploadhandler import FileUploadHandler, StopUpload
from django.db import transaction
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.text import get_valid_filename
from django.views.decorators.http import require_GET, require_POST
from PIL import Image, ImageOps, UnidentifiedImageError
from pypdf import PdfReader
from pypdf.generic import DictionaryObject, ArrayObject, IndirectObject

from .models import Audit, MaintenanceAttachment, MaintenanceRequest
from .maintenance import api_access, requests_for

logger = logging.getLogger(__name__)
MAX_BYTES = 5 * 1024 * 1024
MAX_BATCH = 5
MAX_PER_JOB = 10
MAX_PIXELS = 20_000_000
TYPES = {'JPEG': ('jpg', 'image/jpeg'), 'PNG': ('png', 'image/png'), 'WEBP': ('webp', 'image/webp')}
EXTENSIONS = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.webp': 'WEBP', '.pdf': 'PDF'}


class UploadRejected(ValueError):
    pass


class UploadStorageError(Exception):
    pass


class BoundedUploadHandler(FileUploadHandler):
    """Runs before Django's memory/temp-file handlers, including during CSRF parsing."""
    def __init__(self, request=None):
        super().__init__(request)
        self.total = self.count = self.current = 0
        self.batch_limit = 10 if request and request.path.endswith('/completed-report/') else MAX_BATCH

    def new_file(self, *args, **kwargs):
        super().new_file(*args, **kwargs)
        self.count += 1
        self.current = 0
        if self.count > self.batch_limit:
            self.reject()

    def reject(self):
        self.request.attachment_upload_rejected = True
        raise StopUpload(connection_reset=True)

    def receive_data_chunk(self, raw_data, start):
        self.current += len(raw_data)
        self.total += len(raw_data)
        if self.current > MAX_BYTES or self.total > self.batch_limit * MAX_BYTES:
            self.reject()
        return raw_data

    def file_complete(self, file_size):
        return None


def storage():
    return storages['maintenance_private']


def multipart(request, allowed_fields=()):
    if request.content_type != 'multipart/form-data':
        raise UploadRejected('Use multipart/form-data for attachments.')
    try:
        fields, files = request.POST, request.FILES
    except (RequestDataTooBig, TooManyFilesSent, TooManyFieldsSent):
        raise UploadRejected('Upload exceeds the allowed limits.')
    if getattr(request, 'attachment_upload_rejected', False):
        raise UploadRejected('Maximum five files per upload and 5 MB per file.')
    if set(fields) - set(allowed_fields) or set(files) - {'attachments'}:
        raise UploadRejected('Unexpected upload fields.')
    if any(len(fields.getlist(key)) != 1 for key in fields):
        raise UploadRejected('Repeated report fields are not allowed.')
    uploads = files.getlist('attachments')
    if len(uploads) > MAX_BATCH:
        raise UploadRejected('Maximum five files per upload.')
    return fields.dict(), uploads


def validate_pdf(data):
    if not data.startswith(b'%PDF-') or not data.rstrip().endswith(b'%%EOF'):
        raise UploadRejected('Invalid PDF document.')
    try:
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted or not 1 <= len(reader.pages) <= 100:
            raise UploadRejected('PDF must be unencrypted with 1–100 pages.')
        prohibited = {'/OpenAction', '/AA', '/JS', '/JavaScript', '/Launch', '/EmbeddedFiles',
                      '/EF', '/RichMedia', '/RichMediaContent', '/RichMediaSettings', '/Movie', '/Sound',
                      '/3DD', '/XFA', '/AcroForm', '/A'}
        seen = set()
        stack = [reader.trailer]
        visited = 0
        while stack:
            obj = stack.pop()
            visited += 1
            if visited > 20000:
                raise UploadRejected('PDF is too complex.')
            if isinstance(obj, IndirectObject):
                ref = (obj.idnum, obj.generation)
                if ref in seen:
                    continue
                seen.add(ref)
                stack.append(obj.get_object())
            elif isinstance(obj, DictionaryObject):
                if (prohibited.intersection(obj.keys()) or
                        obj.get('/Subtype') in ('/RichMedia', '/Movie', '/Sound', '/Screen', '/3D', '/Widget') or
                        obj.get('/S') in ('/JavaScript', '/Launch', '/SubmitForm', '/ImportData', '/GoToR', '/GoToE')):
                    raise UploadRejected('PDF forms, actions and embedded content are not supported.')
                stack.extend(obj.values())
            elif isinstance(obj, ArrayObject):
                stack.extend(obj)
    except UploadRejected:
        raise
    except Exception:
        raise UploadRejected('Invalid PDF document.')


def validate_upload(upload):
    if not upload.size or upload.size > MAX_BYTES:
        raise UploadRejected('Each attachment must be nonempty and at most 5 MB.')
    name = str(upload.name)
    if any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise UploadRejected('Invalid attachment filename.')
    name = name.replace('\\', '/').rsplit('/', 1)[-1]
    try:
        name = get_valid_filename(name)
    except Exception:
        raise UploadRejected('Invalid attachment filename.')
    extension = Path(name).suffix.lower()
    expected = EXTENSIONS.get(extension)
    if not expected:
        raise UploadRejected('Only JPEG, PNG, WebP photos and PDF documents are supported.')
    data = upload.read(MAX_BYTES + 1)
    if len(data) != upload.size or len(data) > MAX_BYTES:
        raise UploadRejected('Invalid attachment size.')
    if expected == 'PDF':
        validate_pdf(data)
        suffix, mime = 'pdf', 'application/pdf'
    else:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as image:
                    if image.format != expected or image.width * image.height > MAX_PIXELS:
                        raise UploadRejected('Photo format mismatch or image exceeds 20 megapixels.')
                    if getattr(image, 'n_frames', 1) != 1:
                        raise UploadRejected('Animated images are not supported.')
                    image.load()
                    # Rebuild from pixels: remove EXIF/GPS, metadata and appended content.
                    mode = 'RGBA' if 'A' in image.getbands() or 'transparency' in image.info else 'RGB'
                    if expected == 'JPEG':
                        mode = 'RGB'
                    oriented = ImageOps.exif_transpose(image)
                    clean = Image.new(mode, oriented.size)
                    clean.paste(oriented.convert(mode))
                    oriented.close()
                    output = io.BytesIO()
                    clean.save(output, format=expected)
                    clean.close()
                    data = output.getvalue()
        except UploadRejected:
            raise
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise UploadRejected('Invalid or unsafe photo.')
        suffix, mime = TYPES[expected]
    if len(data) > MAX_BYTES:
        raise UploadRejected('Processed attachment exceeds 5 MB.')
    if upload.content_type not in (mime, 'application/octet-stream'):
        raise UploadRejected('Attachment content type does not match its contents.')
    # Keep only a safe display name; it is never used as a storage path.
    filename = Path(name).stem[:150] + '.' + suffix
    return {'data': data, 'filename': filename, 'content_type': mime, 'suffix': suffix}


def prepare(uploads):
    return [validate_upload(upload) for upload in uploads]


def cleanup(keys):
    for key in keys:
        try:
            storage().delete(key)
        except Exception:
            # No filenames, object keys, tokens or credentials in log messages.
            logger.error('Private attachment rollback cleanup failed; storage reconciliation required.')


def save_files(job, actor, prepared, saved_keys, comment=None, visibility="shared", purpose="general"):
    if purpose == "general" and job.attachments.filter(visibility=visibility, purpose="general").count() + len(prepared) > MAX_PER_JOB:
        raise UploadRejected('Maximum ten attachments per maintenance request.')
    saved_files = []
    for item in prepared:
        attachment_id = uuid.uuid4()
        key = f'maintenance/{job.pk}/{attachment_id}.{item["suffix"]}'
        try:
            saved = storage().save(key, ContentFile(item['data']))
        except Exception:
            raise UploadStorageError from None
        saved_keys.append(saved)
        if saved != key:
            raise UploadStorageError('Storage must preserve server-generated attachment keys.')
        attachment = MaintenanceAttachment.objects.create(id=attachment_id, request=job, uploaded_by=actor,
            comment=comment, visibility=visibility, purpose=purpose, storage_key=key, filename=item['filename'], content_type=item['content_type'],
            size=len(item['data']), sha256=hashlib.sha256(item['data']).hexdigest())
        saved_files.append(attachment)
        Audit.objects.create(agency=job.property.agency, actor=actor,
            action='Maintenance attachment uploaded', object_id=str(attachment_id))
    return saved_files


def visible_attachments(job, user):
    qs = job.attachments.filter(purpose__in=['general','completion_before','completion_after','completion_report'])
    if user.is_superuser:
        return qs
    qs = qs.filter(visibility__in=['shared','agency']).exclude(comment__visibility='internal')
    membership = getattr(user, 'membership', None)
    if membership and membership.role == 'tenant':
        qs=qs.filter(visibility='shared').exclude(comment__visibility='agency')
    if membership and membership.role == 'tenant' and not job.tenant_comments_allowed:
        qs = qs.filter(comment__isnull=True)
    return qs


def attachment_data(attachment):
    return {'id': str(attachment.pk), 'filename': attachment.filename,
            'content_type': attachment.content_type, 'size': attachment.size, 'purpose': attachment.purpose,
            'created_at': attachment.created_at.isoformat(),
            'download_url': reverse('maintenance_attachment_download', args=[attachment.request_id, attachment.pk])}


@api_access
@require_POST
def upload(request, job_id):
    # Authorize before any application validation or private storage writes.
    job = get_object_or_404(requests_for(request.user), pk=job_id)
    keys = []
    try:
        _, uploads = multipart(request)
        if not uploads:
            raise UploadRejected('Choose at least one attachment.')
        prepared = prepare(uploads)
        with transaction.atomic():
            MaintenanceRequest.objects.select_for_update().get(pk=job.pk)
            job = get_object_or_404(requests_for(request.user), pk=job.pk)
            if job.status in ('completed', 'cancelled', 'closed'):
                raise UploadRejected('Attachments cannot be added to a closed request.')
            save_files(job, request.user, prepared, keys)
    except UploadRejected as error:
        cleanup(keys)
        return JsonResponse({'error': str(error)}, status=400)
    except UploadStorageError:
        cleanup(keys)
        return JsonResponse({'error': 'Attachment storage is unavailable. No files were added.'}, status=503)
    except Exception:
        cleanup(keys)
        raise
    return JsonResponse({'attachments': [attachment_data(a) for a in visible_attachments(job, request.user)]}, status=201)


@api_access
@require_GET
def download(request, job_id, attachment_id):
    job = get_object_or_404(requests_for(request.user), pk=job_id)
    attachment = get_object_or_404(visible_attachments(job, request.user), pk=attachment_id)
    return file_response(attachment)


def file_response(attachment):
    """Private streaming helper; callers must first authorize the specific document."""
    try:
        source = storage().open(attachment.storage_key, 'rb')
    except FileNotFoundError:
        raise Http404('Attachment unavailable.')
    except OSError:
        return JsonResponse({'error': 'Attachment storage is unavailable. Try again later.'}, status=503)
    response = FileResponse(source, as_attachment=True, filename=attachment.filename,
                            content_type=attachment.content_type)
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Security-Policy'] = "default-src 'none'; sandbox"
    response['Cross-Origin-Resource-Policy'] = 'same-origin'
    return response
