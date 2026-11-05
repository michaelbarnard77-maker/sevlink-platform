"""Shared validation for manually prepared commercial PDFs. No document generation."""
import hashlib
from datetime import date
from decimal import Decimal, InvalidOperation
from . import attachments

MAX_MONEY = Decimal('9999999999.99')


def money(value):
    if isinstance(value, (bool, float)):
        raise ValueError('Enter the recorded ZAR amount as an exact decimal string.')
    try:
        result = Decimal(str(value))
        if not result.is_finite() or not 0 < result <= MAX_MONEY or result != result.quantize(Decimal('.01')):
            raise ValueError('Enter a positive ZAR amount with at most two decimal places.')
        return result.quantize(Decimal('.01'))
    except (InvalidOperation, TypeError):
        raise ValueError('Invalid ZAR amount.') from None


def text(value, limit, required=True):
    if not isinstance(value, str) or len(value.strip()) > limit or (required and not value.strip()):
        raise ValueError('Invalid document reference or text.')
    if any(ord(c) < 32 and c not in '\n\r\t' for c in value):
        raise ValueError('Invalid control characters.')
    return value.strip()


def day(value):
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError('Use an ISO date: YYYY-MM-DD.')
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError('Use a valid ISO date: YYYY-MM-DD.') from None


def uploaded_pdf(request, fields):
    data, uploads = attachments.multipart(request, fields)
    if len(uploads) != 1:
        raise ValueError('Upload exactly one externally prepared PDF.')
    prepared = attachments.prepare(uploads)
    if prepared[0]['content_type'] != 'application/pdf':
        raise ValueError('A PDF document is required, not a photo or generated quotation.')
    return data, prepared


def file_fingerprint(prepared):
    item = prepared[0]
    return {'filename': item['filename'], 'sha256': hashlib.sha256(item['data']).hexdigest()}


def document_data(document, url):
    return {'id': str(document.pk), 'filename': document.filename, 'size': document.size,
            'uploaded_at': document.created_at.isoformat(), 'sha256': document.sha256, 'download_url': url}
