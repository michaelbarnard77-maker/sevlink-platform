"""Private weekly calendar over the existing assignment/appointment services."""
import hashlib
import json
import uuid
from datetime import datetime, time, timedelta
from decimal import Decimal
from functools import wraps

from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.db.models import F, Sum, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .staff_access import can_schedule, can_pay, staff_only
from .maintenance import payload, TRANSITIONS, update_status
from .models import (MaintenanceRequest, Property, JobAssignment, Subcontractor,
    SubcontractorTeam, TeamAppointment, AppointmentOverride, Province, City, TradeCategory, JobInvoice)
from .regions import coverage, location_values, filter_properties, assign_job
from .suppliers import save_appointment, TZ
from .commercial import day
from .events import record


def checked(view):
    @wraps(view)
    def wrapped(*args,**kwargs):
        try: return view(*args,**kwargs)
        except (ValueError,ValidationError): return JsonResponse({'error':'Invalid scheduling or payment filter fields.'},status=400)
        except IntegrityError: return JsonResponse({'error':'Record changed or duplicate submission. Refresh before retrying.'},status=409)
    return wrapped


def appointment_data(a):
    start=a.starts_at.astimezone(TZ);end=a.ends_at.astimezone(TZ)
    override=AppointmentOverride.objects.filter(appointment=a).first()
    return {'id':a.pk,'job':str(a.assignment.request_id),'reference':a.assignment.request.reference, 'customer_visible':a.customer_visible,
        'property':a.assignment.request.property.address,'status':a.assignment.request.status,
        'status_label':a.assignment.request.get_status_display(),'title':a.assignment.request.title,
        'subcontractor':str(a.team.subcontractor_id),'supplier':a.team.subcontractor.name,
        'team':str(a.team_id),'team_name':a.team.name,'starts_at':start.isoformat(),'ends_at':end.isoformat(),
        'date':str(start.date()),'start':start.strftime('%H:%M'),'end':end.strftime('%H:%M'),
        'left_percent':(start-datetime.combine(start.date(),time(9),tzinfo=TZ)).total_seconds()/60/480*100,
        'width_percent':(end-start).total_seconds()/60/480*100,
        'cancelled':bool(a.cancelled_at),'cancelled_at':a.cancelled_at.isoformat() if a.cancelled_at else None,
        'cancellation_reason':a.cancellation_reason,'rescheduled_from':a.rescheduled_from_id,
        'override':{'reason':override.reason,'actor':override.actor_id,'at':override.created_at.isoformat(),'overlaps':override.overlapping_ids} if override else None}


def appointments():
    return TeamAppointment.objects.select_related('team__subcontractor','assignment__request__property')


@staff_only(can_schedule)
@require_GET
@checked
def week(request):
    start=day(request.GET['week']) if request.GET.get('week') else timezone.localdate()
    start-=timedelta(days=start.weekday());end=start+timedelta(days=7)
    loc=location_values(request.GET)
    suppliers=coverage(Subcontractor.objects.all(),loc)
    if request.GET.get('trade'): suppliers=suppliers.filter(trades__name=request.GET['trade'])
    if request.GET.get('subcontractor'): suppliers=suppliers.filter(pk=uuid.UUID(request.GET['subcontractor']))
    teams=SubcontractorTeam.objects.filter(subcontractor__in=suppliers).select_related('subcontractor')
    if request.GET.get('team'): teams=teams.filter(pk=uuid.UUID(request.GET['team']))
    props=filter_properties(Property.objects.all(),loc)
    qs=appointments().filter(team__in=teams,assignment__request__property__in=props,
        starts_at__gte=datetime.combine(start,time.min,tzinfo=TZ),starts_at__lt=datetime.combine(end,time.min,tzinfo=TZ),cancelled_at__isnull=True)
    search=request.GET.get('job_search','').strip()
    if len(search)>180: raise ValueError
    reference=search.split('-',1)[1] if search.upper().startswith(('SV-','REQ-')) else search
    number_field='request_number' if search.upper().startswith('REQ-') else 'job_number'
    jobs=MaintenanceRequest.objects.exclude(status__in=['completed','cancelled','closed']).filter(
        Q(title__icontains=search)|Q(property__address__icontains=search)|Q(id__icontains=reference)|Q(legacy_job_reference__iexact=search)| (Q(**{number_field:int(reference)}) if reference.isdecimal() and len(reference)<18 else Q(pk__isnull=True)))
    return JsonResponse({'week_start':str(start),'previous':str(start-timedelta(days=7)),'next':str(end),
        'days':[str(start+timedelta(days=i)) for i in range(7)],'timezone':'Africa/Johannesburg',
        'teams':[{'id':str(t.pk),'name':t.name,'subcontractor':str(t.subcontractor_id),'supplier':t.subcontractor.name,
            'active':t.active and t.subcontractor.active and not t.subcontractor.archived,
            'working_days':t.working_days,'day_start':str(t.day_start),'day_end':str(t.day_end),
            'unavailable':[str(d) for d in t.unavailable_dates.filter(date__gte=start,date__lt=end).values_list('date',flat=True)]} for t in teams],
        'appointments':[appointment_data(a) for a in qs.order_by('starts_at','pk')],
        'provinces':list(Province.objects.values('id','name')),'cities':list(City.objects.values('id','name','province_id')),
        'trades':list(TradeCategory.objects.values_list('name',flat=True)),
        'suppliers':[{'id':str(s.pk),'name':s.name} for s in Subcontractor.objects.all()],
        'all_teams':[{'id':str(t.pk),'name':t.name,'subcontractor':str(t.subcontractor_id)} for t in SubcontractorTeam.objects.filter(active=True,subcontractor__active=True,subcontractor__archived=False)],
        'jobs':[{'id':str(j.pk),'reference':j.reference,'title':j.title,'property':j.property.address,'version':j.version} for j in jobs.select_related('property')[:100]],
        'job_count':jobs.count(),'can_override':request.user.is_superuser})


class Rejected(Exception):
    def __init__(self,response): self.response=response


def accept(response):
    if response.status_code>=400: raise Rejected(response)
    return json.loads(response.content)


@staff_only(can_schedule)
@require_POST
@checked
def save(request):
    data=payload(request,('job','version','subcontractor','team','starts_at','ends_at','submission_key','appointment','reason','override_reason','cancel','customer_visible'))
    return save_values(request,data)


def save_values(request,data):
    if 'cancel' in data:
        if set(data)!={'cancel','reason'} or type(data['cancel'])is not int: raise ValueError
        a=get_object_or_404(appointments(),pk=data['cancel'])
        with transaction.atomic():
            Property.objects.select_for_update().get(pk=a.assignment.request.property_id)
            job=MaintenanceRequest.objects.select_for_update().get(pk=a.assignment.request_id)
            a.refresh_from_db();changed=not bool(a.cancelled_at)
            result=save_appointment(request.user,a.team.subcontractor_id,data)
            if result.status_code<400 and changed:
                record(job,request.user,'appointment_changed','calendar-cancel:'+str(a.pk),{'appointment_id':str(a.pk),'action':'cancelled'},private=True)
            return result
    if 'customer_visible' in data and type(data['customer_visible'])is not bool: raise ValueError
    required={'job','version','subcontractor','team','starts_at','ends_at','submission_key'}
    if not required<=set(data) or type(data['version'])is not int: raise ValueError
    if any(not isinstance(data[k],str) for k in required-{'version'}): raise ValueError
    key=uuid.UUID(data['submission_key']);job_id=uuid.UUID(data['job']);supplier_id=uuid.UUID(data['subcontractor']);team_id=uuid.UUID(data['team'])
    fingerprint=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
    try:
        with transaction.atomic():
            first=get_object_or_404(MaintenanceRequest,pk=job_id)
            Property.objects.select_for_update().get(pk=first.property_id)
            job=MaintenanceRequest.objects.select_for_update().get(pk=job_id)
            prior=TeamAppointment.objects.filter(submission_key=key).first()
            if prior:
                if prior.actor_id!=request.user.pk or prior.fingerprint!=fingerprint:
                    return JsonResponse({'error':'Scheduling submission key conflict.'},status=409)
                return JsonResponse(appointment_data(appointments().get(pk=prior.pk)))
            if job.version!=data['version'] or job.status in ('completed','cancelled','closed'):
                return JsonResponse({'error':'Job changed or closed. Refresh before scheduling.'},status=409)
            if job.workflow_version and not getattr(request,'_attendance_authorised',False):
                return JsonResponse({'error':'Confirm the attendance request and public arrival window through the attendance workflow.'},status=409)
            old=None
            if data.get('appointment'):
                if type(data['appointment'])is not int or not isinstance(data.get('reason'),str) or not data['reason'].strip(): raise ValueError
                old=get_object_or_404(appointments(),pk=data['appointment'],assignment__request=job)
                if old.cancelled_at or job.assignments.first().pk!=old.assignment_id:
                    return JsonResponse({'error':'Appointment is no longer current.'},status=409)
            supplier_ids=sorted({supplier_id}|({old.team.subcontractor_id} if old else set()),key=str)
            list(Subcontractor.objects.select_for_update().filter(pk__in=supplier_ids).order_by('pk'))
            if old: accept(save_appointment(request.user,old.team.subcontractor_id,{'cancel':old.pk,'reason':data['reason']}))
            allocation=job.assignments.first()
            replace_assessment=False
            if allocation and not getattr(request,'_assessment_authorised',False):
                from .workflow import assessment_ids
                assessment_appointments=job.attendance_requests.filter(pk__in=assessment_ids(job)).values_list('appointment_id',flat=True)
                replace_assessment=allocation.appointments.filter(cancelled_at=None).exists() and not allocation.appointments.filter(cancelled_at=None).exclude(pk__in=assessment_appointments).exists()
            if replace_assessment or not allocation or allocation.subcontractor_id!=supplier_id or allocation.team_id!=team_id:
                accept(assign_job(request.user,job.pk,{'version':job.version,'subcontractor':str(supplier_id),'team':str(team_id),'submission_key':str(uuid.uuid5(key,'assignment'))},assessment_authorised=getattr(request,'_assessment_authorised',False),replace_assessment=replace_assessment))
                job.refresh_from_db();allocation=job.assignments.first()
            else:
                active=allocation.appointments.filter(cancelled_at__isnull=True)
                if not getattr(request,'_assessment_authorised',False):
                    from .workflow import assessment_ids
                    active=active.exclude(pk__in=job.attendance_requests.filter(pk__in=assessment_ids(job)).values_list('appointment_id',flat=True))
                if active.exists():raise Rejected(JsonResponse({'error':'Use reschedule to change the existing appointment.'},status=409))
            booking={'assignment':allocation.pk,'starts_at':data['starts_at'],'ends_at':data['ends_at']}
            if 'override_reason' in data: booking['override_reason']=data['override_reason']
            response=accept(save_appointment(request.user,supplier_id,booking,attendance_authorised=getattr(request,'_attendance_authorised',False),assessment_authorised=getattr(request,'_assessment_authorised',False),phone_confirmed=getattr(request,'_phone_confirmed',False)))
            entry=TeamAppointment.objects.get(pk=response['id'])
            entry.submission_key=key;entry.fingerprint=fingerprint;entry.rescheduled_from=old;entry.customer_visible=data.get('customer_visible',old.customer_visible if old else False);entry.save(update_fields=['submission_key','fingerprint','rescheduled_from','customer_visible'])
            record(job,request.user,'appointment_changed','calendar:'+str(key),{'appointment_id':str(entry.pk),'action':'rescheduled' if old else 'created'},private=True)
        return JsonResponse(appointment_data(appointments().get(pk=entry.pk)),status=201)
    except Rejected as failure: return failure.response


@staff_only(can_schedule)
@require_GET
@checked
def job_detail(request,job_id):
    job=get_object_or_404(MaintenanceRequest.objects.select_related('property'),pk=job_id)
    from .customer_portal import deposit_state
    return JsonResponse({'deposit_ready':deposit_state(job)['ready'],'id':str(job.pk),'reference':job.reference,'title':job.title,'property':job.property.address,
        'status':job.status,'status_label':job.get_status_display(),'version':job.version,'description':job.description,
        'allowed_statuses':[{'value':s,'label':MaintenanceRequest.Status(s).label} for s in TRANSITIONS[job.status]],
        'history':[{'status':h.status,'at':h.at.isoformat()} for h in job.status_events.all()],
        'appointments':[appointment_data(a) for a in appointments().filter(assignment__request=job).order_by('-created_at','-pk')]})


@staff_only(can_schedule)
@require_POST
@checked
def progress(request,job_id):
    data=payload(request,('status','version'))
    if set(data)!={'status','version'} or type(data['version'])is not int or not isinstance(data['status'],str): raise ValueError
    return update_status(request.user,get_object_or_404(MaintenanceRequest,pk=job_id),data,operations=True)


@staff_only(can_pay)
@require_GET
@checked
def monday(request):
    from .models import Agency
    from .commercial import day,money
    from .invoices import invoice_data
    today=timezone.localdate();upcoming=today+timedelta(days=(0-today.weekday())%7)
    period=request.GET.get('period','monday')
    if period not in ('monday','upcoming','all','overdue','paid'): raise ValueError
    qs=JobInvoice.objects.filter(subcontractor__isnull=False,visibility='internal').annotate(balance=F('amount')-F('paid_amount')+F('refunded_amount'))
    if period!='all':qs=qs.filter(document_status='active')
    if request.GET.get('document_status'):
        if request.GET['document_status'] not in ('active','void'):raise ValueError
        qs=qs.filter(document_status=request.GET['document_status'])
    if period=='paid':qs=qs.filter(balance__lte=0)
    elif period!='all':qs=qs.filter(balance__gt=0)
    if request.GET.get('subcontractor'): qs=qs.filter(subcontractor_id=uuid.UUID(request.GET['subcontractor']))
    if period=='monday': qs=qs.filter(due_date__lte=upcoming)
    elif period=='overdue': qs=qs.filter(due_date__lt=today)
    elif period=='upcoming':qs=qs.filter(due_date__gte=today)
    if request.GET.get('agency'):qs=qs.filter(request__property__agency_id=uuid.UUID(request.GET['agency']))
    if request.GET.get('job'):qs=qs.filter(request_id=uuid.UUID(request.GET['job']))
    if request.GET.get('due_date'):qs=qs.filter(due_date=day(request.GET['due_date']))
    if request.GET.get('payment_date'):qs=qs.filter(payments__paid_on=day(request.GET['payment_date'])).distinct()
    if request.GET.get('invoice_status'):qs=qs.filter(payment_status=request.GET['invoice_status'])
    if request.GET.get('amount'):qs=qs.filter(amount=money(request.GET['amount']))
    total=qs.filter(document_status='active',balance__gt=0).aggregate(amount=Sum('balance'))['amount'] or Decimal('0')
    overdue=qs.filter(document_status='active',balance__gt=0,due_date__lt=today).aggregate(amount=Sum('balance'))['amount'] or Decimal('0')
    page=int(request.GET.get('page','1'))
    if not 1<=page<=1000000: raise ValueError
    return JsonResponse({'today':str(today),'monday':str(upcoming),'period':period,'page':page,'count':qs.count(),
        'outstanding_total':f'{total:.2f}','overdue_total':f'{overdue:.2f}',
        'agencies':list(Agency.objects.values('id','name')),
        'jobs':[{'id':str(j.pk),'name':j.reference} for j in MaintenanceRequest.objects.filter(invoices__subcontractor__isnull=False).distinct()],
        'suppliers':[{'id':str(s.pk),'name':s.name} for s in Subcontractor.objects.all()],
        'results':[dict(invoice_data(i,request.user),supplier_name=i.subcontractor.name,job=str(i.request_id),
            job_number=i.request.reference,overdue=i.document_status=='active' and i.amount-i.paid_amount+i.refunded_amount>0 and i.due_date<today,attention=i.reconciliation_required)
            for i in qs.select_related('subcontractor').order_by('due_date','pk')[(page-1)*50:page*50]]})
