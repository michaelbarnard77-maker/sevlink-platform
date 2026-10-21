"""Internal record IDs only. External accounting references are never rewritten."""
from django.db import transaction
from django.utils import timezone
from .models import DocumentSequence


def allocate(prefix):
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError('Number allocation must share the document transaction.')
    if prefix not in ('SQ','SI'):
        raise ValueError('Unsupported document series.')
    year = timezone.localdate().year
    row, _ = DocumentSequence.objects.get_or_create(prefix=prefix, year=year)
    row = DocumentSequence.objects.select_for_update().get(pk=row.pk)
    if row.last_value >= 9999:
        raise ValueError('Annual four-digit document series exhausted; Operations must review numbering.')
    row.last_value += 1
    row.save(update_fields=['last_value'])
    return f'{prefix}-{year}-{row.last_value:04d}'
