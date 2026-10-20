"""Shared comments and agency quotation decisions backed by real Django records."""
import uuid
import hashlib

from django import forms
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from .events import record
from .maintenance import access, api_access, payload, requests_for
from .models import Audit, JobActivity, JobComment, MaintenanceRequest, Membership


def request_key(request):
    try:
        return uuid.UUID(request.headers.get('Idempotency-Key', ''))
    except (ValueError, AttributeError):
        raise ValueError('A UUID Idempotency-Key header is required.')


def lock_job(user, pk):
    MaintenanceRequest.objects.select_for_update().get(pk=pk)
    return get_object_or_404(requests_for(user), pk=pk)


def comment_data(comment, user):
    from .attachments import attachment_data, visible_attachments
    role, name = comment.author_role, comment.author_name
    return {'id': str(comment.pk), 'text': comment.text,
            'actor': 'Sevlink Operations' if role == 'superadmin' and not user.is_superuser else name,
            'at': comment.created_at.isoformat(), 'visibility': comment.visibility,
            'attachments': [attachment_data(a) for a in visible_attachments(comment.request, user).filter(comment=comment)]}


class CommentForm(forms.Form):
    text = forms.CharField(max_length=2500)


@api_access
@require_POST
def add_comment(request, job_id):
    from . import attachments
    from .quotations import digest
    from .events import actor_identity
    job = get_object_or_404(requests_for(request.user), pk=job_id)
    if access(request.user)[0] == Membership.TENANT and not job.tenant_comments_allowed:
        return JsonResponse({'error': 'Tenant conversation access is not enabled for this job.'}, status=403)
    keys = []
    try:
        key = request_key(request)
        if request.content_type == 'multipart/form-data':
            data, uploads = attachments.multipart(request, ('text', 'visibility'))
        else:
            data, uploads = payload(request, ('text', 'visibility')), []
        form = CommentForm(data)
        if not isinstance(data.get('text'), str) or not form.is_valid():
            raise ValueError('A comment of 1–2500 characters is required.')
        visibility = data.get('visibility', 'shared')
        if visibility not in ('shared', 'internal'):
            raise ValueError('Invalid comment visibility.')
        if visibility == 'internal' and not request.user.is_superuser:
            return JsonResponse({'error': 'Internal notes are for Sevlink Operations only.'}, status=403)
        prepared = attachments.prepare(uploads)
        fingerprint = digest({'text': form.cleaned_data['text'], 'visibility': visibility,
            'files': [(p['filename'], hashlib.sha256(p['data']).hexdigest()) for p in prepared]})
        with transaction.atomic():
            job = lock_job(request.user, job_id)
            if access(request.user)[0] == Membership.TENANT and not job.tenant_comments_allowed:
                return JsonResponse({'error': 'Tenant conversation access is disabled.'}, status=403)
            existing = JobComment.objects.filter(idempotency_key=key).first()
            if existing:
                if existing.author_id != request.user.pk or existing.request_id != job.pk or existing.fingerprint != fingerprint:
                    return JsonResponse({'error': 'Idempotency key conflict.'}, status=409)
                return JsonResponse(comment_data(existing, request.user))
            if prepared and job.status in ('completed', 'cancelled'):
                raise ValueError('Attachments cannot be added to closed requests.')
            role, name = actor_identity(request.user)
            comment = JobComment.objects.create(request=job, author=request.user, author_name=name,
                author_role=role, text=form.cleaned_data['text'], visibility=visibility, fingerprint=fingerprint, idempotency_key=key)
            attachments.save_files(job, request.user, prepared, keys, comment=comment, visibility=visibility)
            record(job, request.user, 'internal_note' if visibility == 'internal' else 'comment_added',
                'comment:' + str(comment.pk), {'comment_id': str(comment.pk), 'text': comment.text})
            Audit.objects.create(agency=job.property.agency, actor=request.user, action='Job comment added', object_id=str(comment.pk))
    except ValueError as error:
        attachments.cleanup(keys)
        return JsonResponse({'error': str(error)}, status=400)
    except attachments.UploadStorageError:
        attachments.cleanup(keys)
        return JsonResponse({'error': 'Private storage is unavailable.'}, status=503)
    except Exception:
        attachments.cleanup(keys)
        raise
    return JsonResponse(comment_data(comment, request.user), status=201)
