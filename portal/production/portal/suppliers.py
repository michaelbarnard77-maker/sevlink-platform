"""Private supplier profiles, compliance PDFs, finance gates and scheduling records."""
import hashlib
import json
import re
import uuid
from datetime import date, time, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from django import forms
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import OuterRef, Subquery
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods, require_POST

from . import attachments
from .maintenance import payload
from .models import (AssignmentReview, AssignmentReviewResolution, ComplianceDocument,
    JobAssignment, MaintenanceRequest, Property, Subcontractor,
    SubcontractorTeam, SubcontractorTerms, SupplierActivity, TeamAppointment,
    TeamUnavailableDate, TradeCategory)
from .regions import operations_only, contractor_data, eligible

TZ = ZoneInfo('Africa/Johannesburg')


def audit(item, actor, action, **details):
    return SupplierActivity.objects.create(subcontractor=item, actor=actor, action=action, details=details)


def current_assignments():
    latest = JobAssignment.objects.filter(request_id=OuterRef('request_id')).values('pk')[:1]
    return JobAssignment.objects.filter(pk=Subquery(latest))


def flag_assignments(actor, reason, **filters):
    for assignment in current_assignments().filter(**filters).exclude(request__status__in=['completed', 'cancelled']):
        AssignmentReview.objects.create(assignment=assignment, actor=actor, reason=reason)


def compliance_state(document):
    if document.expires_on is None:
        return 'no_expiry_recorded'
    days = (document.expires_on - timezone.localdate()).days
    return 'expired' if days < 0 else 'expiring_soon' if days <= 30 else 'current'


def document_data(d):
    return {'id': str(d.pk), 'kind': d.kind, 'title': d.title, 'expires_on': d.expires_on,
        'state': compliance_state(d), 'previous': str(d.previous_id) if d.previous_id else None,
        'superseded': ComplianceDocument.objects.filter(previous=d).exists(),
        'filename': d.filename, 'created_at': d.created_at.isoformat(),
        'url': reverse('supplier_document_pdf', args=[d.subcontractor_id, d.pk])}


def compliance_alerts():
    qs = ComplianceDocument.objects.filter(replacement__isnull=True,
        expires_on__lte=timezone.localdate()+timedelta(days=30)).order_by('expires_on', 'pk')
    return {'count': qs.count(), 'items': [dict(document_data(d), subcontractor=str(d.subcontractor_id),
        name=d.subcontractor.name) for d in qs.select_related('subcontractor')[:50]]}


def appointment_data(a):
    return {'id': a.pk, 'assignment': a.assignment_id, 'starts_at': a.starts_at.isoformat(),
        'ends_at': a.ends_at.isoformat(), 'cancelled_at': a.cancelled_at.isoformat() if a.cancelled_at else None}


def team_data(t):
    return {'id': str(t.pk), 'name': t.name, 'active': t.active, 'version': t.version,
        'working_days': t.working_days, 'day_start': str(t.day_start)[:5], 'day_end': str(t.day_end)[:5],
        'unavailable': [{'id': d.pk, 'date': d.date.isoformat(), 'reason': d.reason} for d in t.unavailable_dates.all()],
        'appointments': [appointment_data(a) for a in t.appointments.order_by('-starts_at')[:100]]}


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Subcontractor
        fields = ['name','contact_person','telephone','whatsapp','email','specialisations','internal_notes']


@operations_only
@require_http_methods(['GET', 'POST'])
def profile(request, subcontractor_id):
    if request.method == 'POST':
        data = payload(request, (*ProfileForm.Meta.fields, 'version','status','trades'))
        if set(data) != set(ProfileForm.Meta.fields) | {'version','status','trades'}:
            raise ValueError
        if type(data['version']) is not int or data['status'] not in ('active','inactive','archived'):
            raise ValueError
        if not isinstance(data['trades'], list) or any(not isinstance(v, str) for v in data['trades']):
            raise ValueError
        categories = list(TradeCategory.objects.filter(pk__in=data['trades']))
        if len(categories) != len(set(data['trades'])):
            raise ValueError
        if any(not isinstance(data[k], str) for k in ProfileForm.Meta.fields):
            raise ValueError
        with transaction.atomic():
            item = get_object_or_404(Subcontractor.objects.select_for_update(), pk=subcontractor_id)
            if item.version != data['version']:
                return JsonResponse({'error': 'Profile changed; refresh before saving.'}, status=409)
            old_status = (item.active, item.archived)
            form = ProfileForm({k:data[k] for k in ProfileForm.Meta.fields}, instance=item)
            if not form.is_valid():
                raise ValueError
            item = form.save(commit=False)
            item.active = data['status'] == 'active'; item.archived = data['status'] == 'archived'
            item.version += 1; item.save(); item.trades.set(categories)
            if old_status != (item.active, item.archived):
                flag_assignments(request.user, 'Subcontractor status changed', subcontractor=item)
            audit(item, request.user, 'Profile updated', status=data['status'])
    item = get_object_or_404(Subcontractor, pk=subcontractor_id)
    from .invoices import invoice_data
    data = contractor_data(item)
    data['invoices'] = [dict(invoice_data(i,request.user),job=str(i.request_id)) for i in item.supplier_invoices.all()]
    data['invoice_jobs'] = [{'id':str(j.pk),'title':j.title} for j in MaintenanceRequest.objects.filter(assignments__subcontractor=item).distinct()]
    data.update({k:getattr(item,k) for k in ProfileForm.Meta.fields})
    data.update(version=item.version, status='archived' if item.archived else 'active' if item.active else 'inactive',
        trades=list(item.trades.values_list('pk',flat=True)), trade_options=list(TradeCategory.objects.values_list('pk',flat=True)),
        teams=[team_data(t) for t in item.teams.all()],
        documents=[document_data(d) for d in item.compliance_documents.all()],
        agreements=[{'id': a.pk, 'commission_percent': str(a.commission_percent) if a.commission_percent is not None else '',
            'rate': str(a.rate) if a.rate is not None else '', 'currency':'ZAR', 'rate_basis':a.rate_basis,
            'terms':a.terms, 'created_at':a.created_at.isoformat()} for a in item.agreements.all()],
        assignments=[{'id': a.pk, 'job':str(a.request_id), 'reference':a.request.reference, 'title':a.request.title,
            'team':a.team.name if a.team_id else 'Legacy / team unallocated', 'team_id':str(a.team_id) if a.team_id else None, 'current':current_assignments().filter(pk=a.pk).exists(), 'at':a.created_at.isoformat(),
            'reviews':[{'id':r.pk,'reason':r.reason,'at':r.created_at.isoformat()}
                for r in a.reviews.filter(resolution__isnull=True)]} for a in item.jobassignment_set.select_related('request','team')[:100]],
        activity=[{'action': a.action, 'at':a.created_at.isoformat(), 'actor':a.actor_id, 'details':a.details}
            for a in item.supplier_activity.all()[:100]])
    return JsonResponse(data)


@operations_only
@require_POST
def agreement(request, subcontractor_id):
    data = payload(request, ('commission_percent','rate','rate_basis','terms','submission_key'))
    if set(data) != {'commission_percent','rate','rate_basis','terms','submission_key'}:
        raise ValueError
    if data['rate_basis'] not in ('hour','visit','fixed') or not isinstance(data['terms'], str) or not data['terms'].strip() or len(data['terms']) > 4000:
        raise ValueError
    numbers = {}
    for key, maximum in [('commission_percent',Decimal('100')),('rate',Decimal('9999999999.99'))]:
        raw = data[key]
        if not isinstance(raw,str): raise ValueError
        if not raw: numbers[key]=None; continue
        try: number = Decimal(raw)
        except InvalidOperation: raise ValueError
        if not number.is_finite() or not 0 <= number <= maximum or number.as_tuple().exponent < -2:
            raise ValueError
        numbers[key] = number
    key = uuid.UUID(str(data['submission_key']))
    with transaction.atomic():
        item = get_object_or_404(Subcontractor.objects.select_for_update(), pk=subcontractor_id)
        prior = SubcontractorTerms.objects.filter(submission_key=key).first()
        values = dict(subcontractor=item, actor=request.user, **numbers, rate_basis=data['rate_basis'],terms=data['terms'])
        if prior:
            if any(getattr(prior,k) != v for k,v in values.items()):
                return JsonResponse({'error':'Agreement submission key conflict.'},status=409)
            return JsonResponse({'id':prior.pk})
        entry = SubcontractorTerms(**values, submission_key=key); entry.full_clean(); entry.save()
        audit(item, request.user, 'Commercial agreement recorded', agreement=entry.pk)
    return JsonResponse({'id':entry.pk},status=201)


@operations_only
@require_POST
def document_upload(request, subcontractor_id):
    keys=[]
    try:
        data, files = attachments.multipart(request, ('kind','title','expires_on','previous','submission_key'))
        if len(files) != 1 or set(data) - {'previous','expires_on'} != {'kind','title','submission_key'}:
            raise ValueError
        kind = data['kind']; title = data['title'].strip()
        if kind not in dict(ComplianceDocument._meta.get_field('kind').choices) or not title or len(title)>180:
            raise ValueError
        expires = forms.DateField(required=False).clean(data.get('expires_on'))
        key = uuid.UUID(data['submission_key'])
        prepared = attachments.validate_upload(files[0])
        if prepared['content_type'] != 'application/pdf': raise ValueError
        digest = hashlib.sha256(prepared['data']).hexdigest()
        fingerprint = hashlib.sha256(json.dumps([kind,title,str(expires),data.get('previous') or '',digest]).encode()).hexdigest()
        with transaction.atomic():
            item = get_object_or_404(Subcontractor.objects.select_for_update(), pk=subcontractor_id)
            prior = ComplianceDocument.objects.filter(submission_key=key).first()
            if prior:
                if prior.subcontractor_id != item.pk or prior.uploaded_by_id != request.user.pk or prior.fingerprint != fingerprint:
                    return JsonResponse({'error':'Document submission key conflict.'},status=409)
                return JsonResponse(document_data(prior))
            previous = get_object_or_404(ComplianceDocument, pk=uuid.UUID(data['previous']), subcontractor=item, kind=kind) if data.get('previous') else None
            if previous and ComplianceDocument.objects.filter(previous=previous).exists():
                return JsonResponse({'error':'Document already replaced.'},status=409)
            doc_id = uuid.uuid4(); storage_key=f'subcontractors/{item.pk}/{doc_id}.pdf'
            try: saved=attachments.storage().save(storage_key,ContentFile(prepared['data']))
            except Exception: raise attachments.UploadStorageError from None
            keys.append(saved)
            if saved != storage_key: raise attachments.UploadStorageError
            doc=ComplianceDocument.objects.create(id=doc_id,subcontractor=item,kind=kind,title=title,expires_on=expires,previous=previous,
                storage_key=storage_key,filename=prepared['filename'],size=len(prepared['data']),sha256=digest,uploaded_by=request.user,
                submission_key=key,fingerprint=fingerprint)
            audit(item, request.user, 'Compliance PDF uploaded', document=str(doc.pk))
        return JsonResponse(document_data(doc),status=201)
    except attachments.UploadStorageError:
        attachments.cleanup(keys)
        return JsonResponse({'error':'Private storage unavailable. No document was recorded.'},status=503)
    except Exception:
        attachments.cleanup(keys)
        raise


@operations_only
@require_http_methods(['GET'])
def document_pdf(request, subcontractor_id, document_id):
    doc=get_object_or_404(ComplianceDocument,pk=document_id,subcontractor_id=subcontractor_id)
    try: source=attachments.storage().open(doc.storage_key,'rb')
    except (FileNotFoundError,OSError): raise Http404('Document unavailable.') from None
    response=FileResponse(source,as_attachment=True,filename=doc.filename,content_type='application/pdf')
    response['X-Content-Type-Options']='nosniff';response['Content-Security-Policy']="default-src 'none'; sandbox"
    response['Cross-Origin-Resource-Policy']='same-origin';response['Cache-Control']='private, no-store'
    audit(doc.subcontractor,request.user,'Compliance PDF accessed',document=str(doc.pk))
    return response


def valid_window(team,start,end):
    start=start.astimezone(TZ);end=end.astimezone(TZ)
    return (start < end and start.date()==end.date() and start.weekday() in team.working_days
        and team.day_start <= start.time().replace(tzinfo=None) < end.time().replace(tzinfo=None) <= team.day_end
        and not team.unavailable_dates.filter(date=start.date()).exists())


@operations_only
@require_POST
def team(request, subcontractor_id):
    data=payload(request,('id','version','name','active','working_days','day_start','day_end'))
    required={'version','name','active','working_days','day_start','day_end'}
    if set(data)-{'id'} != required or type(data['version']) is not int or type(data['active']) is not bool:
        raise ValueError
    if not isinstance(data['name'],str) or not data['name'].strip() or len(data['name'])>100:
        raise ValueError
    days=data['working_days']
    if not isinstance(days,list) or any(type(d)is not int or not 0<=d<=6 for d in days) or len(days)!=len(set(days)):
        raise ValueError
    if not all(isinstance(data[k],str) for k in ('day_start','day_end')): raise ValueError
    start=forms.TimeField(input_formats=['%H:%M']).clean(data['day_start']);end=forms.TimeField(input_formats=['%H:%M']).clean(data['day_end'])
    if not time(9)<=start<end<=time(17): raise ValueError
    with transaction.atomic():
        item=get_object_or_404(Subcontractor.objects.select_for_update(),pk=subcontractor_id)
        t=get_object_or_404(SubcontractorTeam.objects.select_for_update(),pk=uuid.UUID(str(data['id'])),subcontractor=item) if data.get('id') else SubcontractorTeam(subcontractor=item,version=0)
        if t.version!=data['version']: return JsonResponse({'error':'Team changed. Refresh before saving.'},status=409)
        was_active=t.active
        t.name=data['name'].strip();t.active=data['active'];t.working_days=sorted(days);t.day_start=start;t.day_end=end
        if t.pk and not t._state.adding:
            for a in t.appointments.filter(cancelled_at__isnull=True,ends_at__gte=timezone.now()):
                if not t.active or not valid_window(t,a.starts_at,a.ends_at):
                    return JsonResponse({'error':'Existing appointments conflict. Cancel/reschedule them first.'},status=409)
            if was_active and not t.active: flag_assignments(request.user,'Assigned team deactivated',team=t)
        t.version+=1;t.full_clean();t.save()
        audit(item,request.user,'Team availability updated',team=str(t.pk))
    return JsonResponse(team_data(t))


@operations_only
@require_POST
def unavailable(request, subcontractor_id, team_id):
    data=payload(request,('date','reason','remove'))
    if not isinstance(data.get('reason',''),str) or len(data.get('reason',''))>500: raise ValueError
    day=forms.DateField().clean(data.get('date'))
    if 'remove' in data and type(data['remove']) is not bool: raise ValueError
    with transaction.atomic():
        item=get_object_or_404(Subcontractor.objects.select_for_update(),pk=subcontractor_id)
        t=get_object_or_404(SubcontractorTeam.objects.select_for_update(),pk=team_id,subcontractor=item)
        if data.get('remove'):
            t.unavailable_dates.filter(date=day).delete()
        else:
            if any(a.starts_at.astimezone(TZ).date() == day for a in t.appointments.filter(cancelled_at__isnull=True)):
                return JsonResponse({'error':'An appointment exists on this date. Cancel/reschedule it first.'},status=409)
            TeamUnavailableDate.objects.update_or_create(team=t,date=day,defaults={'reason':data.get('reason',''),'actor':request.user})
        t.version+=1;t.save(update_fields=['version'])
        audit(item,request.user,'Unavailable date changed',team=str(t.pk),date=str(day),removed=bool(data.get('remove')))
    return JsonResponse(team_data(t))


@operations_only
@require_POST
def appointment(request, subcontractor_id):
    return save_appointment(request.user,subcontractor_id,payload(request,('assignment','starts_at','ends_at','cancel','reason','override_reason')))


def save_appointment(user,subcontractor_id,data,attendance_authorised=False,assessment_authorised=False,phone_confirmed=False):
    from .staff_access import can_schedule
    if not can_schedule(user): return JsonResponse({'error':'Scheduling access required.'},status=403)
    with transaction.atomic():
        a = None
        if not data.get('cancel'):
            if type(data.get('assignment')) is not int: raise ValueError
            a=get_object_or_404(JobAssignment,pk=data['assignment'],subcontractor_id=subcontractor_id)
            prop=Property.objects.select_for_update().get(pk=a.request.property_id)
            job=MaintenanceRequest.objects.select_for_update().get(pk=a.request_id)
            job.property=prop; a.request=job
            if job.workflow_version and not attendance_authorised:
                return JsonResponse({'error':'Use the confirmed attendance workflow before booking this job.'},status=409)
            from .customer_portal import deposit_state
            from .workflow import free_assessment
            if not deposit_state(job)['ready'] and not (assessment_authorised and attendance_authorised and free_assessment(job)):
                return JsonResponse({'error':'A confirmed 50% customer deposit or an authorised Sevlink scheduling arrangement is required.'},status=409)
        item=get_object_or_404(Subcontractor.objects.select_for_update(),pk=subcontractor_id)
        if data.get('cancel'):
            if set(data)!={'cancel','reason'} or type(data['cancel'])is not int or not isinstance(data['reason'],str) or not data['reason'].strip() or len(data['reason'])>500: raise ValueError
            a=get_object_or_404(TeamAppointment,pk=data['cancel'],team__subcontractor=item)
            SubcontractorTeam.objects.select_for_update().get(pk=a.team_id)
            a=TeamAppointment.objects.select_for_update().get(pk=a.pk)
            if a.cancelled_at: return JsonResponse(appointment_data(a))
            a.cancelled_at=timezone.now();a.cancelled_by=user;a.cancellation_reason=data['reason'];a.save()
            job=a.assignment.request
            if job.workflow_version:
                job.status='reviewed';job.version+=1;job.save(update_fields=['status','version'])
                from .workflow import attention_notifications
                attention_notifications(job,user,'Attendance cancelled',f'attendance-cancel:{a.pk}',tenant=True)
            audit(item,user,'Appointment cancelled',appointment=a.pk)
            return JsonResponse(appointment_data(a))
        if set(data)-{'override_reason'}!={'assignment','starts_at','ends_at'} or type(data['assignment'])is not int: raise ValueError
        if any(not isinstance(data[k],str) for k in ('starts_at','ends_at')): raise ValueError
        start=parse_datetime(data['starts_at']);end=parse_datetime(data['ends_at'])
        if not start or not end or not timezone.is_aware(start) or not timezone.is_aware(end): raise ValueError
        if not a.team_id: return JsonResponse({'error':'Assign a team before recording an appointment.'},status=400)
        t=SubcontractorTeam.objects.select_for_update().get(pk=a.team_id)
        manual=phone_confirmed and attendance_authorised
        if not item.active or item.archived or not t.active or (not manual and not valid_window(t,start,end)): raise ValueError
        if not current_assignments().filter(pk=a.pk).exists() or a.request.status in ('completed','cancelled','closed') or a.reviews.filter(resolution__isnull=True).exists():
            return JsonResponse({'error':'Assignment changed, closed or requires Operations review.'},status=409)
        if not eligible(a.request.property).filter(pk=item.pk).exists(): raise ValueError
        prior_bookings=t.appointments.filter(assignment=a,cancelled_at__isnull=True)
        if attendance_authorised and not assessment_authorised:
            from .workflow import assessment_ids
            prior_bookings=prior_bookings.exclude(pk__in=job.attendance_requests.filter(pk__in=assessment_ids(job)).values_list('appointment_id',flat=True))
        existing=prior_bookings.first()
        if existing:
            if existing.starts_at==start and existing.ends_at==end: return JsonResponse(appointment_data(existing))
            return JsonResponse({'error':'Cancel the existing appointment before rescheduling.'},status=409)
        overlaps=list(t.appointments.filter(cancelled_at__isnull=True,starts_at__lt=end,ends_at__gt=start).values_list('pk',flat=True))
        override=data.get('override_reason','')
        if not isinstance(override,str) or len(override)>1000: raise ValueError
        if override and not user.is_superuser:
            return JsonResponse({'error':'Only Super Admin can authorise an overlap exception.'},status=403)
        if overlaps and not manual and not (user.is_superuser and override.strip()):
            return JsonResponse({'error':'Team already has an overlapping appointment. Super Admin authorisation with a reason is required.'},status=409)
        entry=TeamAppointment.objects.create(assignment=a,team=t,starts_at=start,ends_at=end,actor=user)
        if overlaps and not manual:
            from .models import AppointmentOverride
            AppointmentOverride.objects.create(appointment=entry,actor=user,reason=override.strip(),overlapping_ids=overlaps)
            audit(item,user,'Overlap exception authorised',appointment=entry.pk)
        audit(item,user,'Phone-confirmed booking recorded' if manual else 'Appointment recorded',appointment=entry.pk,assignment=a.pk)
    return JsonResponse(appointment_data(entry),status=201)


@operations_only
@require_POST
def review(request, review_id):
    data=payload(request,('reason',))
    if set(data)!={'reason'} or not isinstance(data['reason'],str) or not data['reason'].strip() or len(data['reason'])>1000: raise ValueError
    with transaction.atomic():
        entry=get_object_or_404(AssignmentReview.objects.select_for_update(),pk=review_id)
        if AssignmentReviewResolution.objects.filter(review=entry).exists():
            return JsonResponse({'error':'Review already resolved.'},status=409)
        AssignmentReviewResolution.objects.create(review=entry,actor=request.user,reason=data['reason'])
        audit(entry.assignment.subcontractor,request.user,'Assignment review acknowledged',review=entry.pk)
    return JsonResponse({'resolved':True})


@operations_only
@require_http_methods(['GET'])
def invoice_ledger(request):
    from .models import JobInvoice
    from .invoices import invoice_data
    from .financial import net_paid
    from .staff_access import can_pay
    if not can_pay(request.user):return JsonResponse({'error':'Super Admin finance access required.'},status=403)
    qs=JobInvoice.objects.filter(subcontractor__isnull=False).select_related('subcontractor','request__property__agency')
    state=request.GET.get('state','outstanding')
    if state not in ('all','outstanding','paid','void'): raise ValueError
    if state=='outstanding': qs=qs.filter(document_status='active').exclude(payment_status='paid')
    elif state=='void': qs=qs.filter(document_status='void')
    elif state=='paid': qs=qs.filter(document_status='active',payment_status='paid')
    page=int(request.GET.get('page','1'))
    if not 1<=page<=1000000: raise ValueError
    return JsonResponse({'count':qs.count(),'page':page,'results':[dict(invoice_data(i,request.user),
        subcontractor=str(i.subcontractor_id),supplier_name=i.subcontractor.name,job=str(i.request_id))
        for i in qs.order_by('due_date','pk')[(page-1)*50:page*50]]})
