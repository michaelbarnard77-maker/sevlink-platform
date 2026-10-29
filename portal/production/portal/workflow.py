"""Saved operational decisions, conservative legacy compatibility and public projections."""
import uuid
import hashlib
from datetime import timedelta
from decimal import Decimal
from functools import wraps
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from .models import (MaintenanceRequest, Membership, WorkflowDecision, UserJobNotification,
    AdditionalAuthorisation, DepositVerification, AttendanceRequest, CompletionRecord,
    JobInvoice, JobQuotation, MaintenanceStatusEvent, User)
from .maintenance import api_access, access, requests_for, payload
from .commercial import money, text, day
from .collaboration import request_key
from .quotations import digest
from .events import record

WINDOWS=('09:00–13:00','12:00–17:00')
STAGES=(('new','New Requests'),('quoting','Quoting'),('approval','Awaiting Quotation Approval'),('declined','Declined'),
        ('deposit','Awaiting Deposit'),('ready','Ready to Schedule'),('booked','Booked Appointments'),
        ('underway','Work Underway'),('invoice','Ready to Invoice'),('payment','Awaiting Final Payment'),('closed','Closed Jobs'))


def notify(event,users):
    for user in users:
        if user and user.is_active:
            UserJobNotification.objects.get_or_create(event=event,user=user)


def managers(job):
    users=list(User.objects.filter(membership__agency=job.property.agency,membership__role='admin',is_active=True))
    if job.property.manager_id:users.append(job.property.manager)
    return users


def operators():
    return User.objects.filter(is_active=True,is_superuser=True)


def access_tenants(job):
    from .models import Tenancy
    users=User.objects.filter(tenancy__property=job.property,tenancy__active=True,is_active=True,membership__role='tenant').distinct()
    if getattr(job.reported_by,'membership',None) and job.reported_by.membership.role=='tenant':
        return list(users.filter(pk=job.reported_by_id))
    return list(users)


def can_arrange(job,user):
    role,_=access(user)
    return user in access_tenants(job) if job.access_responsibility=='sevlink' else role in ('pm','admin')


def attendance_invitation(job,actor,key):
    event=record(job,actor,'workflow_event',key,{'action':'Please confirm attendance date','decision_id':key[:180]})
    notify(event,access_tenants(job) if job.access_responsibility=='sevlink' else managers(job))
    return event


def participants(job,tenant=False):
    result=managers(job)
    if tenant:result.extend(access_tenants(job))
    return result


def effective_quotes(job):
    from .models import QuoteApprovalReplacement
    return job.quotations.filter(status='approved').exclude(pk__in=QuoteApprovalReplacement.objects.values('original_id'))


def assessment_ids(job):
    return [s['assessment_attendance'] for s in job.workflow_decisions.filter(operation__in=('operations-triage','attendance-request')).values_list('snapshot',flat=True) if type(s.get('assessment_attendance')) is int]


def free_assessment(job):
    last=job.workflow_decisions.filter(operation='operations-triage').order_by('-created_at','-pk').first()
    return bool(job.job_type=='quoted' and not job.quotations.exists() and last and last.snapshot.get('decision')=='attendance' and not job.closed_at and job.status not in ('completed','closed','cancelled'))


def eligible(job):
    from .customer_portal import deposit_state
    return (free_assessment(job) or deposit_state(job)['ready']) and not job.closed_at and job.status not in ('completed','cancelled','closed')


def completion_valid(job):
    record=job.completion_records.order_by('-created_at').first()
    if not record:return False
    kinds=set(record.documents.values_list('purpose',flat=True))
    return bool(record.report.strip()) and 'completion_after' in kinds and ('completion_before' in kinds or (record.before_unavailable and record.exception_reason))


def check_ceiling(job,amount,exclude=None):
    if not job.workflow_version:return
    total=job.invoices.filter(visibility='shared',subcontractor=None,document_status='active').exclude(pk=exclude).aggregate(n=Sum('amount'))['n'] or Decimal('0')
    if job.job_type=='callout':
        ceiling=job.spending_limit if job.authorised_at else None
    else:
        ceiling=effective_quotes(job).aggregate(n=Sum('amount'))['n']
    if ceiling is None or total+amount>ceiling:
        raise ValueError('Total active agency-facing invoices exceed the authorised VAT-inclusive amount. Obtain further approval or reconcile externally issued documents first; deposits must not be billed twice.')


def stage(job):
    manual=job.workflow_decisions.filter(operation='manual-stage').order_by('-created_at','-pk').first()
    if manual and manual.snapshot.get('version')==job.version:return manual.snapshot['stage']
    if job.closed_at or job.status=='cancelled':return 'closed'
    if job.status=='completed':
        return 'payment' if job.invoices.filter(purpose='final',visibility='shared',document_status='active').exists() else 'invoice'
    if job.status in ('on_site','attended','in_progress'):return 'underway'
    if job.status=='scheduled' or job.attendance_requests.filter(status='confirmed',appointment__cancelled_at__isnull=True).exclude(pk__in=assessment_ids(job) if not free_assessment(job) else []).exists():return 'booked'
    if job.job_type=='unclassified' and job.workflow_version:return 'new'
    triage=job.workflow_decisions.filter(operation='operations-triage').order_by('-created_at','-pk').first()
    if not job.quotations.exists() and not triage:return 'new'
    if free_assessment(job):return 'ready'
    if job.job_type=='callout':return 'ready' if job.authorised_at else 'new'
    if job.quotations.filter(status='sent').exists():return 'approval'
    if effective_quotes(job).exists():return 'ready' if eligible(job) else 'deposit'
    latest=job.quotations.order_by('-created_at','-pk').first()
    if latest and latest.status=='rejected':return 'declined'
    return 'new' if job.status=='awaiting_review' else 'quoting'


def after_payment(job,actor):
    if not job.workflow_version:return
    finals=job.invoices.filter(visibility='shared',subcontractor=None,purpose='final',document_status='active')
    all_agency=job.invoices.filter(visibility='shared',subcontractor=None,document_status='active')
    settled=finals.exists() and all(i.paid_amount-i.refunded_amount>=i.amount and not i.reconciliation_required for i in all_agency)
    if job.closed_at and not settled:
        job.closed_at=None;job.status='completed';job.version+=1;job.save(update_fields=['closed_at','status','version'])
        MaintenanceStatusEvent.objects.create(request=job,actor=actor,status='completed')
        attention_notifications(job,actor,'Job reopened for financial reconciliation',f'reopened:{job.pk}:{job.version}')
    if job.status=='completed' and completion_valid(job) and settled:
        if not job.closed_at:
            job.closed_at=timezone.now();job.status='closed';job.version+=1;job.save(update_fields=['closed_at','status','version'])
            MaintenanceStatusEvent.objects.create(request=job,actor=actor,status='closed')
            event=record(job,actor,'workflow_event',f'closed:{job.pk}:{job.version}',{'action':'Job closed after final payment','decision_id':str(job.pk)})
            notify(event,participants(job))


def attention_notifications(job,actor,label,key,tenant=False):
    event=record(job,actor,'workflow_event',key,{'action':label,'decision_id':key[:180]})
    notify(event,participants(job,tenant))
    return event


def data(job,user):
    role,_=access(user);staff=user.is_superuser;tenant=role=='tenant'
    arrivals=[dict(id=a.pk,preference=a.preference,requested_date=a.requested_date,requested_window=a.requested_window,
        purpose='assessment' if a.pk in assessment_ids(job) else 'work',status='cancelled' if a.appointment_id and a.appointment.cancelled_at else a.status,appointment_id=a.appointment_id if staff else None,agreed_date=a.agreed_date,agreed_window=a.agreed_window,confirmed_at=a.confirmed_at)
        for a in job.attendance_requests.order_by('-created_at','-pk')]
    from .customer_portal import deposit_state
    manual=job.workflow_decisions.filter(operation='manual-stage').order_by('-created_at','-pk').first()
    return dict(manual_stage=bool(manual and manual.snapshot.get('version')==job.version),
        manual_move_options=[dict(value=k,label=v) for k,v in STAGES] if staff else [],
        free_assessment=free_assessment(job),can_arrange_attendance=can_arrange(job,user),
        operations_triage=(job.workflow_decisions.filter(operation='operations-triage').order_by('-created_at','-pk').values_list('snapshot',flat=True).first() or {}).get('decision'),
        can_triage=staff and job.job_type!='unclassified' and not job.quotations.exists() and not job.closed_at and job.status not in ('completed','cancelled','closed'),
        **({} if tenant else {'deposit':deposit_state(job)}),compatibility=not bool(job.workflow_version),job_type=job.job_type,safety_concern=job.safety_concern,
        **({} if tenant else {'access_responsibility':job.access_responsibility}),access_information=job.access_information,
        spending_limit=None if tenant else str(job.spending_limit) if job.spending_limit is not None else None,
        authorised_at=job.authorised_at,closed_at=job.closed_at,parent_request=str(job.parent_request_id) if job.parent_request_id else None,
        stage=stage(job),attendance_ready=eligible(job),arrival_windows=WINDOWS,attendance=arrivals,
        additional=[] if tenant else [dict(id=a.pk,amount=str(a.amount),reason=a.reason,status=a.status,linked_request=str(a.linked_request_id) if a.linked_request_id else None,decided_at=a.decided_at) for a in job.additional_authorisations.all()],
        completion=[dict(report=c.report,before_unavailable=c.before_unavailable,exception_reason=c.exception_reason,created_at=c.created_at) for c in job.completion_records.all()],
        history=[] if tenant else [dict(action=d.operation,at=d.created_at,actor='Sevlink Operations' if d.actor.is_staff else d.actor.get_full_name() or 'Agency user',details=d.snapshot) for d in job.workflow_decisions.select_related('actor').all() if staff or d.operation!='manual-stage'])


def tab_attention(job,user,visible):
    """Counts use the same authorised documents/comments as the job response.

    Opening a tab acknowledges recipient notifications, never a business action.
    An outstanding item takes precedence over its unread update to avoid counting
    one quote/invoice/attendance action twice. No new read-state model is needed.
    """
    role,_=access(user)
    tenant=role=='tenant';staff=user.is_superuser;pm=role in ('pm','admin')
    counts=dict(overview=0,comments=0,attendance=0,activity=0,reports=0)
    if not tenant:counts.update(quotes=0,invoices=0)
    if staff:counts['costs']=0
    unread={key:[] for key in counts}
    w=visible['workflow'];terminal=job.status in ('completed','closed','cancelled')
    if pm and not terminal:
        counts['overview']=int(job.status=='awaiting_review')+sum(a['status']=='pending' for a in w['additional'])
        counts['attendance']=int(w['can_arrange_attendance'] and w['attendance_ready'] and not any(a['status'] in ('pending','confirmed') for a in w['attendance']))
    elif staff and not terminal:
        counts['attendance']=sum(a['status']=='pending' for a in w['attendance'])
    quotes={q['id']:q for q in visible['quotations']}
    invoices={i['id']:i for i in visible['invoices']}
    comments={c['id'] for c in visible['comments']}
    if not tenant:
        actionable=('draft','sent','rejected','revision_requested') if staff else ('sent',)
        counts['quotes']=sum(q['status'] in actionable and not q['has_next_revision'] and not q['superseded_by_approval'] for q in quotes.values())
        for invoice in invoices.values():
            if invoice['document_status']=='active' and Decimal(invoice['outstanding'])>0:
                key='costs' if invoice.get('visibility')=='internal' else 'invoices'
                if key in counts:counts[key]+=1
    updates={'Please confirm attendance date':'attendance','Attendance arrangements requested':'attendance',
        'Alternative attendance date being arranged':'attendance','Attendance confirmed':'attendance',
        'Alternative attendance confirmed':'attendance','Completion report and photographs available':'reports'}
    notices=UserJobNotification.objects.filter(user=user,event__request=job,read_at=None).exclude(event__actor=user).select_related('event')
    for notice in notices:
        e=notice.event;key=None
        if e.kind in ('comment_added','internal_note'):
            if e.details.get('comment_id') in comments:key='comments'
        elif e.kind=='quote_sent' and e.details.get('quote_id') in quotes:key='quotes'
        elif e.kind.startswith('invoice_') and e.details.get('invoice_id') in invoices:
            key='costs' if invoices[e.details['invoice_id']].get('visibility')=='internal' else 'invoices'
        elif e.kind=='workflow_event':
            key=updates.get(e.details.get('action'))
            # Only a currently eligible PM may receive a private readiness signal.
            if e.visibility!='shared' and not staff and not (pm and key=='attendance' and w['attendance_ready']):key=None
        elif e.kind in ('status_changed','job_cancelled','job_completed') and (staff or e.visibility=='shared'):
            key='activity'
        if key in unread:unread[key].append(notice.pk)
    # Quote/invoice badges describe unresolved records, not stale upload alerts.
    for key in ('comments','reports','activity'):
        counts[key]=len(unread[key])
    if not counts['attendance']:counts['attendance']=len(unread['attendance'])
    return dict(counts=counts,unread=unread)


def checked(view):
    @wraps(view)
    def wrapped(*args,**kwargs):
        try:return view(*args,**kwargs)
        except ValueError as e:return JsonResponse({'error':str(e)},status=400)
    return wrapped


@api_access
@require_GET
def dashboard(request):
    rows=list(requests_for(request.user))
    grouped={key:[] for key,label in STAGES}
    for job in rows:grouped[stage(job)].append(job)
    definitions=STAGES
    attention=[]
    if access(request.user)[0] in ('pm','admin'):
        from .customer_portal import attention_rows,public_appointments
        confirmed=set(public_appointments(request.user).filter(cancelled_at=None).values_list('assignment__request_id',flat=True))
        grouped['booked']=[job for job in grouped['booked'] if job.pk in confirmed]
        attention=attention_rows(request.user)
        ids={item['job'] for item in attention}
        grouped['attention']=[job for job in rows if str(job.pk) in ids]
        definitions=(('attention','Needs Your Attention'),('new','New Requests'),('approval','Awaiting Quote Approval'),('deposit','Awaiting Deposit'),('booked','Booked'),('underway','Work Underway'),('payment','Awaiting Final Payment'),('closed','Closed'))
    attention_by_job={}
    for item in attention:
        attention_by_job.setdefault(item['job'],[]).append({key:item[key] for key in ('action','amount','due_date','appointment_date') if key in item})
    selected=request.GET.get('stage','')
    if selected and selected not in dict(definitions):return JsonResponse({'error':'Unknown stage.'},status=400)
    result=grouped[selected] if selected else rows
    upcoming=AttendanceRequest.objects.filter(request__in=rows,status='confirmed',agreed_date__gte=timezone.localdate(),appointment__cancelled_at__isnull=True).exclude(request__status__in=['completed','closed','cancelled']).select_related('request__property').order_by('agreed_date')[:12]
    summary=None
    if request.user.is_superuser:
        today=timezone.localdate()
        summary=[dict(label='New today',count=sum(timezone.localtime(j.created_at).date()==today for j in rows)),dict(label='Urgent attention',count=sum(j.urgency in ('urgent','safety') and j.status not in ('cancelled','completed','closed') for j in rows)),dict(label='Visits today',count=AttendanceRequest.objects.filter(request__in=rows,status='confirmed',agreed_date=today,appointment__isnull=False,appointment__cancelled_at__isnull=True).exclude(request__status__in=['completed','closed','cancelled']).count()),dict(label='Waiting on Sevlink',count=sum(len(grouped[k]) for k in ('quoting','ready','underway','invoice')))]
    return JsonResponse({'summary':summary,'upcoming':[dict(id=str(a.request_id),reference=a.request.reference,property=a.request.property.address,date=a.agreed_date,window=a.agreed_window) for a in upcoming], 'attention_action_count':len(attention), 'stages':[dict(key=k,label=label,count=len(grouped[k])) for k,label in definitions],
        'results':[dict(id=str(j.pk),reference=j.reference,title=j.title,property=j.property.address,property_name=j.property.name,agency=j.property.agency.name,category=j.category,urgency=j.urgency,safety_concern=j.safety_concern,status=j.get_status_display(),attention_actions=attention_by_job.get(str(j.pk),[])) for j in result]})


@api_access
@require_GET
def inbox(request):
    qs=UserJobNotification.objects.filter(user=request.user,event__request__in=requests_for(request.user)).select_related('event__request__property')
    return JsonResponse({'unread':qs.filter(read_at=None).count(),'results':[dict(id=n.pk,read=bool(n.read_at),at=n.created_at,
        reference=n.event.request.reference,property=n.event.request.property.address,job=str(n.event.request_id),
        label=n.event.details.get('action',n.event.get_kind_display())) for n in qs[:200]]})


@api_access
@require_POST
@checked
def mark_read(request,notification_id):
    n=get_object_or_404(UserJobNotification,user=request.user,pk=notification_id,event__request__in=requests_for(request.user))
    values=payload(request,('read',))
    if type(values.get('read'))is not bool:raise ValueError('Specify read as true or false.')
    n.read_at=timezone.now() if values['read'] else None;n.save(update_fields=['read_at'])
    return JsonResponse({'read':bool(n.read_at)})


def review_request(job,actor,values):
    """Shared validation for PM review and direct PM submission, within a transaction."""
    reason=text(values.get('reason',''),2500,False)
    kind=values.get('job_type');urgency=values.get('urgency');responsibility=values.get('access_responsibility')
    if kind not in ('callout','quoted') or urgency not in ('normal','high','urgent') or responsibility not in ('sevlink','pm'):raise ValueError('Select job type, urgency and access responsibility.')
    if job.authorised_at or effective_quotes(job).exists():raise ValueError('An authorised job requires the additional-authorisation workflow; its original approval cannot be overwritten.')
    if job.job_type!='unclassified' and not reason:raise ValueError('Record a reason for changing the review.')
    job.workflow_version=1;job.job_type=kind;job.urgency=urgency;job.access_responsibility=responsibility
    job.access_information=text(values.get('access_information',''),2500,False)
    if kind=='callout':
        job.spending_limit=money(values.get('limit'));job.authorised_by=actor;job.authorised_at=timezone.now()
        from .numbering import approve_job_number
        approve_job_number(job)
    job.status='reviewed'
    MaintenanceStatusEvent.objects.create(request=job,actor=actor,status='reviewed')


@api_access
@require_POST
@checked
def action(request,job_id,operation):
    if operation=='review':
        if access(request.user)[0] not in ('pm','admin'):return JsonResponse({'error':'Authorised property manager required.'},status=403)
        get_object_or_404(requests_for(request.user),pk=job_id)
    keys=[]
    try:
        key=request_key(request)
        prepared=[]
        if operation=='review' and request.content_type=='multipart/form-data':
            from . import attachments
            values,files=attachments.multipart(request,('version','job_type','urgency','access_responsibility','access_information','limit','reason'))
            if not values.get('version','').isdigit():raise ValueError('A current job version is required.')
            values['version']=int(values['version']);prepared=attachments.prepare(files)
        else:
            values=payload(request,('version','job_type','urgency','access_responsibility','access_information','limit','reason','additional','decision','date','window','preference','confirmation','report','before_unavailable','exception_reason'))
        allowed={'operations-triage':{'decision'},'review':{'job_type','urgency','access_responsibility','access_information','limit','reason'},'additional-request':{'limit','reason'},'additional-decision':{'additional','decision'},'verify-deposit':{'confirmation'},'attendance-request':{'preference','date','window'},'attendance-decline':{'additional','reason'},'completion':{'report','before_unavailable','exception_reason'}}
        if operation not in allowed or set(values)-{'version'}-allowed[operation]:raise ValueError('Unexpected fields for this workflow action.')
        fingerprint=digest(dict(values,operation=operation,job=str(job_id),**({'photos':[(p['filename'],hashlib.sha256(p['data']).hexdigest()) for p in prepared]} if prepared else {})))
        with transaction.atomic():
            job=get_object_or_404(requests_for(request.user).select_for_update(of=('self',)),pk=job_id)
            prior=WorkflowDecision.objects.filter(key=key).first()
            if prior:
                if prior.request_id!=job.pk or prior.actor_id!=request.user.pk or prior.fingerprint!=fingerprint:return JsonResponse({'error':'Submission key conflict.'},status=409)
                return JsonResponse(data(job,request.user))
            if values.get('version')!=job.version or type(values.get('version'))is not int:return JsonResponse({'error':'Job changed. Refresh before deciding.'},status=409)
            if job.closed_at or job.status=='cancelled':return JsonResponse({'error':'The job is closed.'},status=409)
            role,_=access(request.user);pm=role in ('pm','admin');staff=request.user.is_superuser
            if operation in ('review','additional-decision') and not pm:return JsonResponse({'error':'Authorised property manager or agency administrator required.'},status=403)
            if operation=='attendance-request' and not (can_arrange(job,request.user) or (staff and free_assessment(job))):return JsonResponse({'error':'This attendance request belongs to the designated access contact.'},status=403)
            if operation not in ('review','additional-decision','attendance-request') and not staff:return JsonResponse({'error':'Sevlink Super Admin access required.'},status=403)
            if operation in ('additional-decision','attendance-decline') and (type(values.get('additional'))is not int or values['additional']<1):raise ValueError('A valid saved decision reference is required.')
            reason=text(values.get('reason',''),2500,False)
            if operation=='review':
                review_request(job,request.user,values)
                if prepared:attachments.save_files(job,request.user,prepared,keys,visibility='shared',purpose='general')
            elif operation=='operations-triage':
                if job.job_type=='unclassified' or job.quotations.exists():raise ValueError('Only a forwarded request without a quotation can be assessed.')
                if values.get('decision') not in ('desktop','attendance'):raise ValueError('Choose attendance needed or desktop quote.')
                if values['decision']=='attendance' and job.job_type=='quoted':
                    pending=job.attendance_requests.filter(status='pending').first()
                    if pending and pending.pk not in assessment_ids(job):raise ValueError('Resolve the existing work attendance request first.')
                    if pending:values['assessment_attendance']=pending.pk
                elif values['decision']=='desktop' and job.attendance_requests.filter(status='pending',pk__in=assessment_ids(job)).exists():
                    raise ValueError('Arrange or decline the pending assessment visit before switching to desktop quoting.')
            elif operation=='additional-request':
                if job.job_type!='callout' or not job.authorised_at:raise ValueError('An authorised call-out is required.')
                limit=money(values.get('limit'))
                if limit<=job.spending_limit:raise ValueError('Specify a higher total spending ceiling.')
                AdditionalAuthorisation.objects.create(request=job,amount=limit,reason=text(reason,2500),requested_by=request.user)
            elif operation=='additional-decision':
                item=get_object_or_404(AdditionalAuthorisation.objects.select_for_update(),pk=values.get('additional'),request=job)
                if item.status!='pending':return JsonResponse({'error':'A decision already exists.'},status=409)
                decision=values.get('decision')
                if decision not in ('approved','declined','quotation'):raise ValueError('Choose approve, decline or separate quotation.')
                item.status=decision;item.decided_by=request.user;item.decided_at=timezone.now()
                if decision=='approved':
                    if item.amount<=job.spending_limit:raise ValueError('This authorisation is stale; a higher limit is already active.')
                    job.spending_limit=item.amount
                if decision=='quotation':
                    item.linked_request=MaintenanceRequest.objects.create(property=job.property,reported_by=request.user,parent_request=job,
                        title='Additional work: '+job.title[:160],description=item.reason,category=job.category,job_type='quoted',workflow_version=1,status='reviewed',access_responsibility=job.access_responsibility)
                    record(item.linked_request,request.user,'job_submitted','linked:'+str(key),{'status':'reviewed'})
                item.save()
            elif operation=='verify-deposit':
                if values.get('confirmation')!='VERIFY':raise ValueError('Confirm the received and allocated deposit explicitly.')
                from .customer_portal import deposit_state
                state=deposit_state(job)
                if (job.job_type!='quoted' and job.workflow_version) or not effective_quotes(job).exists() or Decimal(state['received'])<Decimal(state['required']) or Decimal(state['required'])<=0:raise ValueError('Approved quotation and sufficient staff-recorded, confirmed receipts are required.')
                if job.invoices.filter(visibility='shared',reconciliation_required=True,document_status='active').exists():raise ValueError('Resolve the financial reconciliation hold first.')
                DepositVerification.objects.create(request=job,verified_by=request.user,amount=Decimal(state['received']))
            elif operation=='attendance-request':
                if not eligible(job):return JsonResponse({'error':'Attendance arrangements are locked until the applicable authorisation milestone.'},status=409)
                if job.attendance_requests.filter(status='pending').exists():raise ValueError('An attendance request is already awaiting Operations.')
                pref=values.get('preference')
                if pref not in ('date','call'):raise ValueError('Choose a preferred date or request a call.')
                when=day(values.get('date')) if pref=='date' else None
                window=values.get('window','') if pref=='date' else ''
                if when and (when<timezone.localdate() or window not in WINDOWS):raise ValueError('Choose a future date and one of the two arrival windows.')
                item=AttendanceRequest.objects.create(request=job,requested_by=request.user,preference=pref,requested_date=when,requested_window=window)
                if free_assessment(job):values['assessment_attendance']=item.pk
            elif operation=='attendance-decline':
                item=get_object_or_404(AttendanceRequest.objects.select_for_update(),pk=values.get('additional'),request=job)
                if item.status!='pending':raise ValueError('This attendance request is no longer pending.')
                if not reason:raise ValueError('Record why an alternative date must be arranged.')
                item.status='declined';item.save(update_fields=['status'])
            elif operation=='completion':
                report=text(values.get('report'),5000)
                docs=job.attachments.filter(purpose__in=['completion_before','completion_after','completion_report'])
                if not docs.filter(purpose='completion_after',content_type__startswith='image/').exists():raise ValueError('After-work photographs are required.')
                exception=values.get('before_unavailable') is True
                exception_reason=text(values.get('exception_reason',''),1000,False)
                if exception and not exception_reason:raise ValueError('Record the reason before-work photographs are unavailable.')
                if not docs.filter(purpose='completion_before').exists() and not (exception and exception_reason):raise ValueError('Before-work photos or a confirmed reason for their absence are required.')
                completion=CompletionRecord.objects.create(request=job,recorded_by=request.user,report=report,before_unavailable=exception,exception_reason=exception_reason)
                completion.documents.set(docs)
                from .completion_delivery import maybe_queue
                maybe_queue(job,request.user)
            else:return JsonResponse({'error':'Unknown workflow action.'},status=404)
            job.version+=1;job.save()
            snapshot={k:v for k,v in values.items() if k!='version'}
            decision=WorkflowDecision.objects.create(request=job,actor=request.user,operation=operation,key=key,fingerprint=fingerprint,snapshot=snapshot)
            labels={'operations-triage':'Sevlink assessment route selected','review':'Request reviewed and routed','additional-request':'Additional spending authorisation requested','additional-decision':'Additional spending decision recorded','verify-deposit':'Deposit verified','attendance-request':'Attendance arrangements requested','attendance-decline':'Alternative attendance date being arranged','completion':'Completion report and photographs available'}
            event=record(job,request.user,'workflow_event','workflow:'+str(key),{'action':labels[operation],'decision_id':str(decision.pk)},private=operation in ('additional-request','additional-decision','review','verify-deposit'))
            notify(event,operators() if operation=='attendance-request' or pm else participants(job,operation=='completion'))
            if (operation=='review' and job.job_type=='callout') or operation=='verify-deposit' or (operation=='operations-triage' and values.get('decision')=='attendance'):
                attendance_invitation(job,request.user,'ready:'+str(key))
        return JsonResponse(data(job,request.user))
    except Exception as error:
        from .attachments import cleanup,UploadStorageError
        cleanup(keys)
        if isinstance(error,UploadStorageError):return JsonResponse({'error':'Photo storage is unavailable. No photos or forwarding changes were saved.'},status=503)
        raise


@api_access
@require_POST
@checked
def documents(request,job_id):
    from . import attachments
    if not request.user.is_superuser:return JsonResponse({'error':'Sevlink Super Admin required.'},status=403)
    job=get_object_or_404(requests_for(request.user),pk=job_id);keys=[]
    try:
        values,files=attachments.multipart(request,('kind',))
        kind=values.get('kind')
        if kind not in ('completion_before','completion_after','completion_report'):raise ValueError('Choose before photos, after photos or completion report.')
        prepared=attachments.prepare(files)
        if not prepared:raise ValueError('Select documents to upload.')
        if kind!='completion_report' and any(not p['content_type'].startswith('image/') for p in prepared):raise ValueError('Photographs must be images.')
        with transaction.atomic():
            job=get_object_or_404(requests_for(request.user).select_for_update(of=('self',)),pk=job_id)
            if job.closed_at:raise ValueError('Closed job documents are retained; new uploads are blocked.')
            attachments.save_files(job,request.user,prepared,keys,purpose=kind)
        return JsonResponse({'saved':len(prepared)},status=201)
    except Exception:
        attachments.cleanup(keys);raise


@api_access
@require_POST
@checked
def confirm_attendance(request,job_id):
    """Confirm public arrival information and private calendar booking atomically."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from django.utils.dateparse import parse_datetime
    from .models import Property
    from .staff_access import can_schedule
    from . import scheduling
    if not can_schedule(request.user):return JsonResponse({'error':'Sevlink scheduling access required.'},status=403)
    v=payload(request,('version','attendance','date','window','client_confirmed','contact_category','subcontractor','team','starts_at','ends_at','appointment','reason','override_reason'))
    if type(v.get('attendance'))is not int or v['attendance']<1:raise ValueError('A saved attendance request is required.')
    if any(not isinstance(v.get(k),str) for k in ('starts_at','ends_at')):raise ValueError('Actual private booking times are required.')
    key=request_key(request);fingerprint=digest(dict(v,job=str(job_id)))
    first=get_object_or_404(MaintenanceRequest,pk=job_id)
    if request.user.is_superuser is False and access(request.user)[0]!='operations':return JsonResponse({'error':'Operations access required.'},status=403)
    try:
        with transaction.atomic():
            Property.objects.select_for_update().get(pk=first.property_id)
            job=MaintenanceRequest.objects.select_for_update().get(pk=job_id)
            prior=WorkflowDecision.objects.filter(key=key).first()
            if prior:
                if prior.request_id!=job.pk or prior.actor_id!=request.user.pk or prior.fingerprint!=fingerprint:return JsonResponse({'error':'Submission key conflict.'},status=409)
                return JsonResponse({'confirmed':True})
            if type(v.get('version'))is not int or v['version']!=job.version:return JsonResponse({'error':'Job changed; refresh.'},status=409)
            if not eligible(job):return JsonResponse({'error':'Attendance is locked.'},status=409)
            item=get_object_or_404(AttendanceRequest.objects.select_for_update(),pk=v.get('attendance'),request=job)
            if item.status=='confirmed' and v.get('appointment')!=item.appointment_id:raise ValueError('Reschedule the current confirmed appointment; do not replace a different visit.')
            assessment=item.pk in assessment_ids(job)
            if assessment and not free_assessment(job):raise ValueError('This assessment visit is no longer open for booking. Arrange work attendance separately.')
            when=day(v.get('date'));window=v.get('window')
            if when<timezone.localdate() or window not in WINDOWS:raise ValueError('Select a future date and an allowed arrival window.')
            alternative=item.preference=='call' or item.status!='pending' or when!=item.requested_date or window!=item.requested_window or bool(v.get('appointment'))
            if alternative and (v.get('client_confirmed')is not True or v.get('contact_category')not in ('tenant','pm','other')):raise ValueError('Confirm the date with the client/tenant and record who was contacted before rescheduling.')
            start=parse_datetime(v.get('starts_at',''));end=parse_datetime(v.get('ends_at',''))
            if not start or not end or not timezone.is_aware(start) or not timezone.is_aware(end):raise ValueError('Record actual private booking start/end times separately.')
            local=start.astimezone(ZoneInfo('Africa/Johannesburg'))
            if local.date()!=when or not ((540<=local.hour*60+local.minute<=780) if window==WINDOWS[0] else (720<=local.hour*60+local.minute<1020)):raise ValueError('Private booking arrival must fall within the agreed public arrival window.')
            booking={k:v[k] for k in ('version','subcontractor','team','starts_at','ends_at')}
            booking.update(job=str(job.pk),submission_key=str(key),customer_visible=True)
            for k in ('appointment','reason','override_reason'):
                if k in v:booking[k]=v[k]
            request._attendance_authorised=True
            request._assessment_authorised=assessment
            response=scheduling.save_values(request,booking)
            if response.status_code>=400:raise scheduling.Rejected(response)
            import json
            appointment_id=json.loads(response.content)['id']
            item.status='confirmed';item.agreed_date=when;item.agreed_window=window;item.contact_category=v.get('contact_category','') if alternative else ''
            item.confirmed_by=request.user;item.confirmed_at=timezone.now();item.appointment_id=appointment_id;item.save()
            job.refresh_from_db();job.status='reviewed' if assessment else 'scheduled';job.version+=1;job.save(update_fields=['status','version'])
            MaintenanceStatusEvent.objects.create(request=job,actor=request.user,status=job.status)
            WorkflowDecision.objects.create(request=job,actor=request.user,key=key,fingerprint=fingerprint,operation='attendance-confirm',snapshot=dict(purpose='assessment' if assessment else 'work',**{k:v[k] for k in ('date','window','contact_category','client_confirmed') if k in v}))
            attention_notifications(job,request.user,'Free quotation assessment confirmed' if assessment else 'Attendance confirmed' if not alternative else 'Alternative attendance confirmed','attendance:'+str(key),tenant=True)
        return JsonResponse({'confirmed':True},status=201)
    except scheduling.Rejected as e:return e.response


def refresh_overdue(actor):
    """Run from a local scheduler/worker. Time-derived, persisted and deduplicated."""
    if not actor.is_superuser:raise ValueError('Super Admin actor required.')
    count=0
    for invoice in JobInvoice.objects.filter(subcontractor__isnull=False,visibility='internal',document_status='active',due_date__lt=timezone.localdate()):
        if invoice.amount-invoice.paid_amount+invoice.refunded_amount<=0:continue
        with transaction.atomic():
            event=record(invoice.request,actor,'workflow_event',f'supplier-overdue:{invoice.pk}:{invoice.due_date}',{'action':'Private subcontractor invoice overdue','decision_id':str(invoice.pk)},private=True)
            notify(event,operators());count+=1
    return count


@api_access
@require_GET
@checked
def agencies(request):
    from .models import Agency,Property,Tenancy,RemovalReceipt
    if not request.user.is_superuser:return JsonResponse({'error':'Super Admin access required.'},status=403)
    qs=Agency.objects.all()
    if request.GET.get('agency'):qs=qs.filter(pk=uuid.UUID(request.GET['agency']))
    return JsonResponse({'pending_cleanups':[dict(id=str(r.pk),kind=r.kind,files=len(r.pending_files)) for r in RemovalReceipt.objects.exclude(pending_files=[])], 'agencies':[dict(id=str(a.pk),name=a.name,properties=[dict(id=str(p.pk),address=p.address,manager=p.manager.get_full_name() if p.manager_id else None,tenants=[dict(id=str(t.pk),name=t.name,linked=bool(t.user_id)) for t in p.tenancy_set.filter(active=True)],jobs=[dict(id=str(j.pk),reference=j.reference,title=j.title,status=j.get_status_display()) for j in p.maintenance_requests.all()]) for p in Property.objects.filter(agency=a).select_related('manager')]) for a in qs]})
