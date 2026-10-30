"""Customer workspace projections. Private supplier models are never serialized."""
from datetime import timedelta
from functools import wraps
from decimal import Decimal, ROUND_UP
from django import forms
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from .maintenance import api_access, access, properties_for, requests_for, payload
from .models import (Membership, JobInvoice, JobQuotation, TeamAppointment, JobActivity,
    PortalAcknowledgement, JobActionRequest, SchedulingArrangement, WebsiteIssue, Audit, Tenancy)

ZERO=Decimal('0.00')
CLOSED=('completed','cancelled','closed')


def checked(view):
    @wraps(view)
    def wrapped(*args,**kwargs):
        try:return view(*args,**kwargs)
        except (ValueError,forms.ValidationError):
            return JsonResponse({'error':'Invalid customer workspace request.'},status=400)
    return wrapped


def customer(request, finance=False):
    role,_=access(request.user)
    return role in ((Membership.ADMIN,Membership.PM) if finance else (Membership.ADMIN,Membership.PM,Membership.TENANT))


def job_row(job):
    return dict(job=str(job.pk),reference=job.reference,property=job.property.address,
                title=job.title,status=job.status,status_label=job.get_status_display())


def shared_invoices(user):
    return JobInvoice.objects.filter(request__in=requests_for(user),visibility='shared',subcontractor=None).select_related('request__property','document')


def deposit_state(job):
    invoices=job.invoices.filter(visibility='shared',subcontractor=None,document_status='active')
    amount=invoices.aggregate(value=Sum('amount'))['value'] or ZERO
    paid=invoices.aggregate(value=Sum('paid_amount'))['value'] or ZERO
    refunded=invoices.aggregate(value=Sum('refunded_amount'))['value'] or ZERO
    # Preserve the effective approved amount while an amendment awaits a decision.
    from .models import QuoteApprovalReplacement
    approved=job.quotations.filter(status='approved').exclude(pk__in=QuoteApprovalReplacement.objects.values('original_id')).aggregate(value=Sum('amount'))['value']
    basis=approved if approved is not None else amount
    required=(basis*Decimal('0.50')).quantize(Decimal('.01'),rounding=ROUND_UP)
    net=paid-refunded
    arranged=job.scheduling_arrangements.exists()
    held=invoices.filter(reconciliation_required=True).exists()
    verified=job.deposit_verifications.order_by('-created_at').first()
    if job.workflow_version:
        if job.job_type=='callout':ready=bool(job.authorised_at and job.spending_limit)
        else:ready=bool(approved is not None and job.job_number and not held and (arranged or (verified and verified.amount>=required and net>=required and required>ZERO)))
    elif invoices.filter(purpose='deposit').exists():
        # New deposit invoices on historical jobs follow the explicit verification
        # gate too; historical payments and existing invoice purposes are untouched.
        ready=bool(approved is not None and job.job_number and not held and (arranged or (verified and verified.amount>=required and net>=required and required>ZERO)))
    else:ready=arranged or (basis>ZERO and net>=required and not held)
    blockers=[]
    verification_required=bool(job.workflow_version or invoices.filter(purpose='deposit').exists()) and job.job_type!='callout'
    if verification_required:
        if approved is None:blockers.append('The quotation must be approved.')
        if net<required or required<=ZERO:blockers.append('The required deposit has not been received.')
        if held:blockers.append('The invoice has a reconciliation hold.')
        if not arranged and (not verified or verified.amount<required):blockers.append('The recorded payment still needs explicit Sevlink deposit verification.')
        if not job.job_number:blockers.append('The approved request needs its official job number allocated.')
    return dict(basis=str(basis),required=str(required),received=str(net),
                outstanding=str(max(ZERO,required-net)),arrangement=arranged,
                ready=ready,verification_recorded=bool(verified and verified.amount>=required and required>ZERO),blockers=blockers)


def public_appointments(user):
    return TeamAppointment.objects.filter(customer_visible=True,assignment__request__in=requests_for(user)).select_related('assignment__request__property').order_by('starts_at','pk')


def appointment_row(a):
    job=a.assignment.request
    state='cancelled' if a.cancelled_at else 'rescheduled' if a.rescheduled_from_id else 'scheduled'
    if job.workflow_version and hasattr(a,'public_arrival'):
        arrival=a.public_arrival
        return dict(job_row(job),id=a.pk,starts_at=str(arrival.agreed_date)+'T'+arrival.agreed_window.split('–')[0]+':00+02:00',ends_at=str(arrival.agreed_date)+'T'+arrival.agreed_window.split('–')[1]+':00+02:00',appointment_status=state,changed_at=(a.cancelled_at or a.created_at).isoformat())
    return dict(job_row(job),id=a.pk,starts_at=a.starts_at.isoformat(),ends_at=a.ends_at.isoformat(),
                appointment_status=state,changed_at=(a.cancelled_at or a.created_at).isoformat())


def appointment_key(a):
    return f'appointment:{a.pk}:{(a.cancelled_at or a.created_at).isoformat()}'


def attention_rows(user):
    role,_=access(user)
    finance=role in (Membership.ADMIN,Membership.PM)
    result=[];now=timezone.now();today=timezone.localdate();deposits={}
    def deposit(job):
        if job.pk not in deposits:deposits[job.pk]=deposit_state(job)
        return deposits[job.pk]
    def add(job,key,action,priority=5,**details):
        result.append(dict(job_row(job),key=key,action=action,priority=0 if (job.urgency in ('urgent','safety') or (job.safety_concern and job.job_type=='unclassified')) and job.status not in CLOSED else priority,
                           **details))
    qs=requests_for(user)
    if finance:
        for q in JobQuotation.objects.filter(request__in=qs,status='sent').select_related('request__property'):
            add(q.request,'quote:'+str(q.pk),'Review revised quotation' if q.revision>1 or q.amends_id else 'Approve, reject or request quotation revision',
                2,amount=str(q.amount),target='quotation',target_id=str(q.pk))
        from .invoices import pending_payment_report
        for i in shared_invoices(user).filter(document_status='active',reconciliation_required=False):
            if pending_payment_report(i):continue
            net=i.paid_amount-i.refunded_amount;balance=i.amount-net
            if balance<=0:continue
            state=deposit(i.request);required=Decimal(state['required']);received=Decimal(state['received'])
            cash_met=required>ZERO and received>=required
            overdue=i.due_date<today
            if i.reconciliation_required:action='Invoice requires Sevlink reconciliation review'
            elif i.request.status=='completed':action='Completed job: final payment outstanding'
            elif overdue:action='Overdue invoice: payment required'
            elif not cash_met and not state['arrangement'] and i.request.status not in CLOSED:action='Deposit required before scheduling'
            elif cash_met:action='Deposit threshold received; remaining balance outstanding'
            else:action='Invoice balance outstanding'
            add(i.request,'invoice:'+str(i.pk),action,1 if overdue else 3 if i.request.status not in CLOSED else 5,
                target='invoice',target_id=str(i.pk),amount=str(balance),due_date=str(i.due_date),deposit_received=cash_met)
        from .workflow import eligible,can_arrange,assessment_ids,free_assessment
        for job in qs:
            confirmed=job.attendance_requests.filter(status='confirmed',appointment__isnull=False,appointment__cancelled_at__isnull=True)
            if not free_assessment(job):confirmed=confirmed.exclude(pk__in=assessment_ids(job))
            if job.workflow_version and can_arrange(job,user) and eligible(job) and not job.attendance_requests.filter(status='pending').exists() and not confirmed.exists():
                add(job,'attendance-ready:'+str(job.pk),'Please confirm attendance date',3,target='job')
        # PM attention is limited to decisions/payments/attendance requiring their response.
        # Bookings, new requests and informational updates remain in their own views.
        return sorted({row['key']:row for row in result}.values(),key=lambda r:(r['priority'],r.get('due_date') or '9999',r['key']))
    for job in qs.filter(urgency__in=['urgent','safety']).exclude(status__in=CLOSED):
        if not any(r['job']==str(job.pk) for r in result):add(job,'urgency:'+str(job.pk),'Review urgent maintenance / safety concern',0,target='job')
    # No private appointment times or internal cancellation/override reasons leave this service.
    public=public_appointments(user)
    successors=set(public.filter(rescheduled_from__isnull=False).values_list('rescheduled_from_id',flat=True))
    ack=set(PortalAcknowledgement.objects.filter(user=user).values_list('key',flat=True))
    for a in public:
        if a.pk in successors or a.assignment.request.status in CLOSED:continue
        key=appointment_key(a)
        if key in ack or (not a.cancelled_at and a.ends_at<now):continue
        add(a.assignment.request,key,'Appointment cancelled' if a.cancelled_at else 'Appointment rescheduled' if a.rescheduled_from_id else 'Upcoming maintenance appointment',
            4,target='appointment',target_id=a.pk,appointment_date=appointment_row(a)['starts_at'],acknowledge=True)
    audience='pm' if finance else 'tenant'
    for item in JobActionRequest.objects.filter(request__in=qs,audience=audience,resolved_at=None).exclude(request__status__in=CLOSED).select_related('request__property'):
        add(item.request,'action:'+str(item.pk),item.text,1 if item.due_date and item.due_date<today else 5,
            target='action',target_id=item.pk,due_date=str(item.due_date) if item.due_date else None)
    # Stable identity per underlying action; derived items disappear as soon as saved state resolves them.
    return sorted({row['key']:row for row in result}.values(),key=lambda r:(r['priority'],r.get('due_date') or r.get('appointment_date') or '9999',r['key']))


@api_access
@checked
@require_GET
def section(request,section):
    if not customer(request):return JsonResponse({'error':'Customer workspace access required.'},status=403)
    finance=customer(request,finance=True)
    if section=='attention':return JsonResponse({'items':attention_rows(request.user)})
    if section=='calendar':
        try:start=forms.DateField().clean(request.GET.get('week',str(timezone.localdate())))
        except forms.ValidationError:return JsonResponse({'error':'Invalid calendar date.'},status=400)
        start-=timedelta(days=start.weekday());end=start+timedelta(days=7)
        rows=[appointment_row(a) for a in public_appointments(request.user) if start<=timezone.localtime(a.starts_at).date()<end]
        return JsonResponse({'week':str(start),'previous':str(start-timedelta(days=7)),'next':str(end),
                             'days':[str(start+timedelta(days=n)) for n in range(7)],'appointments':rows})
    if section=='accounts':
        if not finance:return JsonResponse({'error':'Agency finance access required.'},status=403)
        from .invoices import invoice_data
        choice=request.GET.get('filter','all')
        if choice not in ('all','unpaid','deposit','partial','paid','overdue','cancelled'):return JsonResponse({'error':'Invalid invoice filter.'},status=400)
        rows=[];outstanding=overdue=ZERO;today=timezone.localdate();deposits={}
        for i in shared_invoices(request.user):
            net=i.paid_amount-i.refunded_amount;balance=i.amount-net if i.document_status=='active' else ZERO
            if i.request_id not in deposits:deposits[i.request_id]=deposit_state(i.request)
            job_deposit=deposits[i.request_id]
            exact_deposit=Decimal(job_deposit['required'])>ZERO and Decimal(job_deposit['received'])==Decimal(job_deposit['required']) and net>ZERO
            state='cancelled' if i.document_status=='void' else 'paid' if balance<=0 else 'unpaid' if net<=0 else 'deposit' if exact_deposit else 'partial'
            late=balance>0 and i.due_date<today
            if choice!='all' and not (late if choice=='overdue' else (state=='cancelled' or i.credit_notes.exists()) if choice=='cancelled' else (exact_deposit and i.document_status=='active') if choice=='deposit' else state==choice or (choice=='partial' and state=='deposit')):continue
            outstanding+=balance;overdue+=balance if late else ZERO
            rows.append(dict(job_row(i.request),invoice=invoice_data(i,request.user),finance_state=state,overdue=late,job_deposit=job_deposit))
        return JsonResponse({'invoices':rows,'outstanding':str(outstanding),'overdue':str(overdue),'currency':'ZAR'})
    if section=='quotations':
        if not finance:return JsonResponse({'error':'Agency quotation access required.'},status=403)
        from .quotations import quote_data
        return JsonResponse({'quotations':[dict(job_row(q.request),quotation=quote_data(q,request.user)) for q in JobQuotation.objects.filter(request__in=requests_for(request.user)).exclude(status='draft').select_related('request__property')]})
    if section in ('properties','tenants','profile'):
        role,m=access(request.user);props=properties_for(request.user).select_related('manager','agency')
        from .maintenance import property_data
        if section=='properties':return JsonResponse({'properties':[dict(property_data(p),edit_url=f'/properties/{p.pk}/edit/' if finance else None,invite_url=f'/properties/{p.pk}/tenant/' if finance else None) for p in props]})
        if section=='tenants':
            if not finance:return JsonResponse({'error':'Agency tenant management required.'},status=403)
            return JsonResponse({'tenants':[dict(id=str(t.pk),name=t.name,email=t.email,phone=t.phone,property=t.property.address,linked=bool(t.user_id)) for t in Tenancy.objects.filter(property__in=props,active=True).select_related('property')]})
        return JsonResponse({'name':m.agency.name,'phone':m.agency.phone,'area':m.agency.area,'account_access_url':f'/accounts/{m.agency_id}/' if role=='admin' else None})
    if section=='updates':
        from .events import activity_data
        events=JobActivity.objects.filter(request__in=requests_for(request.user),visibility='shared').select_related('request__property').order_by('-created_at')
        if not finance:events=events.exclude(kind__startswith='quote_').exclude(kind__startswith='invoice_').exclude(kind='comment_added',request__tenant_comments_allowed=False)
        ack=set(PortalAcknowledgement.objects.filter(user=request.user).values_list('key',flat=True))
        rows=[dict(job_row(e.request),event=activity_data(e,request.user),key='event:'+str(e.pk),read='event:'+str(e.pk) in ack) for e in events[:200]]
        for a in public_appointments(request.user):
            row=appointment_row(a);key=appointment_key(a)
            rows.append(dict(row,key=key,read=key in ack,event={'type':'appointment','label':'Appointment '+row['appointment_status'],
                'actor':'Sevlink Operations','at':row['changed_at'],'details':{'starts_at':row['starts_at'],'ends_at':row['ends_at']}}))
        return JsonResponse({'updates':sorted(rows,key=lambda r:r['event']['at'],reverse=True)[:200]})
    if section=='issues':
        return JsonResponse({'issues':[dict(id=str(i.pk),subject=i.subject,status=i.status,created_at=i.created_at.isoformat()) for i in WebsiteIssue.objects.filter(reporter=request.user).order_by('-created_at')]})
    return JsonResponse({'error':'Unknown workspace page.'},status=404)


@api_access
@checked
@require_POST
def acknowledge(request):
    if not customer(request):return JsonResponse({'error':'Customer access required.'},status=403)
    data=payload(request,('key',));key=data.get('key')
    if not isinstance(key,str) or len(key)>160:return JsonResponse({'error':'Invalid acknowledgement.'},status=400)
    allowed={appointment_key(a) for a in public_appointments(request.user)}
    if key.startswith('event:'):
        from uuid import UUID
        try:event=JobActivity.objects.get(pk=UUID(key[6:]),request__in=requests_for(request.user),visibility='shared')
        except (ValueError,JobActivity.DoesNotExist):return JsonResponse({'error':'Update unavailable.'},status=404)
        role,_=access(request.user)
        if role=='tenant' and (event.kind.startswith(('quote_','invoice_')) or (event.kind=='comment_added' and not event.request.tenant_comments_allowed)):
            return JsonResponse({'error':'Update unavailable.'},status=404)
        allowed.add(key)
    if key not in allowed and not PortalAcknowledgement.objects.filter(user=request.user,key=key).exists():
        return JsonResponse({'error':'Action unavailable.'},status=404)
    PortalAcknowledgement.objects.get_or_create(user=request.user,key=key)
    return JsonResponse({'saved':True})


@api_access
@checked
@require_POST
def report_issue(request):
    if not customer(request):return JsonResponse({'error':'Customer access required.'},status=403)
    data=payload(request,('subject','description'))
    class IssueForm(forms.ModelForm):
        class Meta:model=WebsiteIssue;fields=['subject','description']
    if any(not isinstance(data.get(key),str) for key in ('subject','description')):return JsonResponse({'error':'Enter a subject and description.'},status=400)
    form=IssueForm(data)
    if not form.is_valid():return JsonResponse({'error':'Enter a subject and description.'},status=400)
    _,m=access(request.user);issue=form.save(commit=False);issue.reporter=request.user;issue.agency=m.agency;issue.save()
    return JsonResponse({'id':str(issue.pk),'status':issue.status},status=201)


@api_access
@checked
@require_http_methods(['GET','POST'])
def action(request,job_id):
    if request.method=='GET':
        job=get_object_or_404(requests_for(request.user),pk=job_id)
        role,_=access(request.user)
        return JsonResponse({'deposit':deposit_state(job) if role!='tenant' else None,
            'actions':[{'id':a.pk,'text':a.text,'audience':a.audience,'resolved':bool(a.resolved_at)}
                for a in job.action_requests.all() if role=='superadmin' or a.audience==('tenant' if role=='tenant' else 'pm')]})
    data=payload(request,('text','audience','due_date','resolve','urgency','arrangement','customer_visible','appointment'))
    with transaction.atomic():
        job=get_object_or_404(requests_for(request.user).select_for_update(of=('self',)),pk=job_id)
        role,_=access(request.user)
        if 'resolve' in data:
            try:pk=int(data['resolve'])
            except (TypeError,ValueError):return JsonResponse({'error':'Invalid action.'},status=400)
            item=get_object_or_404(JobActionRequest.objects.select_for_update(),pk=pk,request=job)
            allowed=request.user.is_superuser or (item.audience=='pm' and role in ('pm','admin')) or (item.audience=='tenant' and role=='tenant')
            if not allowed:return JsonResponse({'error':'This action is assigned to a different role.'},status=403)
            if not item.resolved_at:item.resolved_at=timezone.now();item.resolved_by=request.user;item.save(update_fields=['resolved_at','resolved_by'])
        elif 'urgency' in data:
            if role not in ('superadmin','admin','pm'):return JsonResponse({'error':'Manager access required.'},status=403)
            if data['urgency'] not in ('normal','urgent','safety'):return JsonResponse({'error':'Invalid urgency.'},status=400)
            if job.workflow_version:return JsonResponse({'error':'Use the audited Review and Route Request workflow.'},status=409)
            job.urgency=data['urgency'];job.save(update_fields=['urgency'])
        else:
            if not request.user.is_superuser:return JsonResponse({'error':'Sevlink Operations access required.'},status=403)
            if 'arrangement' in data:
                reason=data['arrangement']
                if not isinstance(reason,str) or not 1<=len(reason.strip())<=500:return JsonResponse({'error':'A reviewed scheduling-arrangement reason is required.'},status=400)
                SchedulingArrangement.objects.get_or_create(request=job,actor=request.user,reason=reason.strip())
            elif 'customer_visible' in data:
                if type(data['customer_visible'])is not bool:return JsonResponse({'error':'Choose whether this appointment is shared.'},status=400)
                if type(data.get('appointment'))is not int:return JsonResponse({'error':'Invalid appointment.'},status=400)
                a=get_object_or_404(TeamAppointment.objects.select_for_update(),pk=data['appointment'],assignment__request=job)
                if a.customer_visible and not data['customer_visible']:
                    return JsonResponse({'error':'Cancel or reschedule a shared appointment; do not silently remove its history.'},status=409)
                a.customer_visible=data['customer_visible'];a.save(update_fields=['customer_visible'])
            else:
                text=data.get('text');audience=data.get('audience')
                if not isinstance(text,str) or not 1<=len(text.strip())<=500 or audience not in ('pm','tenant'):return JsonResponse({'error':'Enter a safe request and audience.'},status=400)
                if data.get('due_date') is not None and not isinstance(data['due_date'],str):return JsonResponse({'error':'Invalid due date.'},status=400)
                try:due=forms.DateField(required=False).clean(data.get('due_date'))
                except forms.ValidationError:return JsonResponse({'error':'Invalid due date.'},status=400)
                JobActionRequest.objects.get_or_create(request=job,text=text.strip(),audience=audience,resolved_at=None,defaults={'created_by':request.user,'due_date':due})
        Audit.objects.create(agency=job.property.agency,actor=request.user,action='Customer workspace action updated',object_id=str(job.pk))
    return JsonResponse({'saved':True})


@api_access
@checked
@require_GET
def operations_issues(request):
    if not request.user.is_superuser:return JsonResponse({'error':'Sevlink Operations required.'},status=403)
    return JsonResponse({'issues':[dict(id=str(i.pk),subject=i.subject,description=i.description,status=i.status,created_at=i.created_at.isoformat(),agency=i.agency.name if i.agency else '') for i in WebsiteIssue.objects.select_related('agency').order_by('-created_at')[:200]]})
