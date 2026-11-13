"""Private editable job handover notes, with separate concurrency and immutable history."""
import hashlib
import json
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from .staff_access import staff_only,can_schedule
from .models import MaintenanceRequest,JobInternalNoteRevision,Audit
from .maintenance import payload
from .collaboration import request_key


def revision_data(revision):
    return dict(version=revision.version,text=revision.text,
        author=(revision.author.get_full_name() or revision.author.email) if revision.author_id else 'Previously saved note',
        updated_at=revision.created_at.isoformat() if revision.version else None)


def note_data(job):
    latest=job.internal_note_revisions.select_related('author').first()
    return dict(text=job.internal_notes,version=latest.version if latest else 0,
        author=revision_data(latest)['author'] if latest else None,
        updated_at=revision_data(latest)['updated_at'] if latest else None,
        history_count=max(0,job.internal_note_revisions.count()-1))


@staff_only(can_schedule)
@require_http_methods(['GET','POST'])
def note(request,job_id):
    job=get_object_or_404(MaintenanceRequest,pk=job_id)
    if request.method=='GET':
        data=note_data(job)
        if request.GET.get('history')=='1':
            try:
                page=int(request.GET.get('page','1'))
                if page<1 or page>100000:raise ValueError()
            except (ValueError,TypeError):return JsonResponse({'error':'Invalid history page.'},status=400)
            previous=job.internal_note_revisions.exclude(version=data['version']).select_related('author')
            rows=list(previous[(page-1)*25:page*25+1])
            data.update(history=[revision_data(row) for row in rows[:25]],page=page,has_next=len(rows)>25)
        return JsonResponse(data)
    try:
        values=payload(request,('text','version'))
        key=request_key(request)
        if not isinstance(values.get('text'),str) or len(values['text'])>6000 or type(values.get('version')) is not int or values['version']<0:
            raise ValueError('Enter a note of up to 6,000 characters and its current version.')
        fingerprint=hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()
        with transaction.atomic():
            job=get_object_or_404(MaintenanceRequest.objects.select_for_update(),pk=job.pk)
            previous=JobInternalNoteRevision.objects.filter(key=key).first()
            if previous:
                if previous.request_id!=job.pk or previous.author_id!=request.user.pk or previous.fingerprint!=fingerprint:
                    return JsonResponse({'error':'Submission key conflict. Your draft has not been saved.'},status=409)
                return JsonResponse(note_data(job))
            latest=job.internal_note_revisions.first()
            version=latest.version if latest else 0
            if values['version']!=version:
                return JsonResponse({'error':'Another staff member updated this note. Your draft has been kept. Copy your changes before reopening the latest note.'},status=409)
            if latest is None and job.internal_notes:
                JobInternalNoteRevision.objects.create(request=job,version=0,text=job.internal_notes)
            JobInternalNoteRevision.objects.create(request=job,author=request.user,version=version+1,
                text=values['text'],key=key,fingerprint=fingerprint)
            # Do not increment the workflow version: doing so would invalidate a manual stage override.
            job.internal_notes=values['text'];job.updated_at=timezone.now()
            job.save(update_fields=['internal_notes','updated_at'])
            Audit.objects.create(agency=job.property.agency,actor=request.user,action='Job internal note saved',object_id=str(job.pk))
            return JsonResponse(note_data(job))
    except ValueError as error:
        return JsonResponse({'error':str(error)},status=400)
