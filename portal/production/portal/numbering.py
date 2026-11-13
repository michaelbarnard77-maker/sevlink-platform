"""Request/job sequences and reservations for manually entered PDF references."""
from django.db import transaction
from .models import DocumentSequence


def next_number(prefix):
    if prefix not in ('SV', 'REQ') or not transaction.get_connection().in_atomic_block:
        raise RuntimeError('Reference allocation requires the saved-event transaction.')
    row, _ = DocumentSequence.objects.get_or_create(prefix=prefix, year=0)
    row = DocumentSequence.objects.select_for_update().get(pk=row.pk)
    row.last_value += 1
    row.save(update_fields=['last_value'])
    return row.last_value


def approve_job_number(job):
    """Caller holds the job lock. Allocate only after a saved, authorised approval."""
    from .models import MaintenanceRequest
    if job.job_number is None:
        if not job.quotations.filter(status='approved').exists() and not (job.job_type=='callout' and job.authorised_at and job.authorised_by_id):
            raise ValueError('An approved quotation is required before issuing a job number.')
        value = next_number('SV')
        if MaintenanceRequest.objects.filter(pk=job.pk, job_number__isnull=True).update(job_number=value) != 1:
            raise RuntimeError('Job numbering changed without the required job lock.')
        job.job_number = value
    return job.job_number


def reserve_quote_reference(reference, series_id):
    from .models import QuotationReferenceReservation, JobQuotation
    normalized = reference.strip().casefold()
    if not normalized:
        raise ValueError('Enter the quotation reference printed on the uploaded PDF.')
    if JobQuotation.objects.filter(reference__iexact=reference.strip()).exclude(series_id=series_id).exists():
        raise ValueError('This quotation reference is already used by another quotation series.')
    reservation, _ = QuotationReferenceReservation.objects.get_or_create(reference=normalized, defaults={'series_id':series_id})
    if reservation.series_id != series_id:
        raise ValueError('This quotation reference belongs to another quotation series or conflicts with historical records. Use its revision workflow or a new unique reference.')
