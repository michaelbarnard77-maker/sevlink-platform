"""Private-client records, single-purpose email links and scoped client access."""
import hashlib
import json
import secrets
import uuid
from datetime import timedelta
from django import forms
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.db import transaction, IntegrityError
from django.db.models import F, Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import content_disposition_header
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_GET, require_POST
from django.views.decorators.debug import sensitive_post_parameters
from .models import (PrivateClient, PrivateClientLink, User, Membership, Agency, Property,
                     MaintenanceRequest, MailQueue, JobQuotation, SchedulingArrangement, Audit)
from .services import digest, limited
from .maintenance import api_access, payload, serialize


def open_work(client):
    return client.jobs.filter(closed_at=None).exclude(status__in=['closed','cancelled']).filter(Q(job_type='callout')|Q(quotations__status='approved')).exists()


def retire_links(qs):
    now=timezone.now()
    ids=list(qs.filter(revoked_at=None).values_list('message_id',flat=True))
    qs.filter(revoked_at=None).update(revoked_at=now)
    MailQueue.objects.filter(pk__in=ids,sent_at=None,retired_at=None).update(retired_at=now,error_code='link_revoked',body='[Revoked client link removed]')


def issue_link(client,job,purpose,quote=None):
    retire_links(PrivateClientLink.objects.filter(client=client,request=job,purpose=purpose,used_at=None))
    token=secrets.token_urlsafe(48)
    link=PrivateClientLink.objects.create(client=client,request=job,purpose=purpose,quotation=quote,
        quote_version=quote.version if quote else 0,email=client.email,token_hash=digest(token),
        expires_at=timezone.now()+timedelta(days=7 if purpose=='quote' else 2))
    url=settings.SITE_URL+reverse('private_client_link',args=[token])
    if purpose=='quote':
        subject='Sevlink quotation '+quote.reference
        body=f'Hello {client.name},\n\nYour quotation for {job.property.address} is ready.\nReview the original PDF and accept or decline using this secure link:\n{url}\n\nQuotation: {quote.reference} · Revision {quote.revision}\nAmount: ZAR {quote.amount}\nThis link expires in 7 days. Opening it does not accept the quotation.'
    else:
        subject='Activate your Sevlink private-client portal'
        body=f'Hello {client.name},\n\nYour Sevlink portal is ready for {job.property.address}.\nSet your password and activate access here:\n{url}\n\n'
        body+=('After activation, choose your preferred attendance date in your job. Your call-out is ready for scheduling.' if job.job_type=='callout' else 'You can view your quotes, invoices, attendance and comments. Scheduling opens after Sevlink authorises the payment terms and any required deposit is verified.')
        body+='\n\nThis activation link expires in 48 hours. If unexpected, ignore this email.'
    link.message=MailQueue.objects.create(recipient=client.email,subject=subject,body=body,expires_at=link.expires_at,private_job=job)
    link.save(update_fields=['message'])
    return link


def portal_message(client,job,subject,text,section=None):
    url=settings.SITE_URL+reverse('private_client_portal')+'?job='+str(job.pk)+(('&section='+section) if section else '')
    return MailQueue.objects.create(recipient=client.email,subject='Sevlink '+subject,private_job=job,
        body=f'Hello {client.name},\n\n{text}\n\nProperty: {job.property.address}\nJob: {job.reference}\nSign in to your private-client portal:\n{url}')


def activate_or_notify(client,job):
    if not client.portal_active or not client.user.is_active:
        issue_link(client,job,'activate')
    elif job.job_type=='callout':
        portal_message(client,job,'choose your preferred attendance date','Your call-out is authorised. Choose a preferred attendance date; Sevlink confirms the final booking.',section='attendance')
    else:
        portal_message(client,job,'job ready','Your authorised job is available in your portal. Scheduling follows the applicable payment terms.')


def handle_event(event):
    job=event.request;client=job.private_client
    if event.kind=='quote_sent':
        quote=job.quotations.get(pk=event.details['quote_id'])
        issue_link(client,job,'quote',quote)
    elif event.kind=='quote_approved':
        activate_or_notify(client,job)
    elif event.kind=='invoice_uploaded' and event.visibility!='internal':
        portal_message(client,job,'invoice available','A new invoice is available. Use Paid to report payment; Sevlink verifies received money.',section='invoices')
    elif event.kind=='comment_added' and event.visibility=='shared' and event.actor_id!=client.user_id:
        portal_message(client,job,'new message','Sevlink has added a message to your job. Sign in to read and reply.',section='comments')
    elif event.kind=='workflow_event':
        label=event.details.get('action','')
        if label=='Please confirm attendance date':
            if client.portal_active and client.user.is_active:portal_message(client,job,'choose your preferred attendance date','Your job is ready for attendance arrangements. Choose a preferred date in the Attendance section. Sevlink confirms the final booking.',section='attendance')
        elif label=='Job reopened for financial reconciliation':activate_or_notify(client,job)
        elif label=='Free quotation assessment confirmed':
            arrival=job.attendance_requests.filter(status='confirmed').order_by('-created_at').first()
            if arrival:MailQueue.objects.create(recipient=client.email,subject='Sevlink assessment confirmed',body=f'Hello {client.name},\n\nYour free quotation assessment at {job.property.address} is confirmed for {arrival.agreed_date}, {arrival.agreed_window}.\nPlease contact maintenance@sevlink.co.za if you need assistance.')
        elif client.portal_active and label in ('Attendance confirmed','Alternative attendance confirmed','Appointment on site','Appointment complete','Completion report and photographs available'):
            portal_message(client,job,'job update',label+'. Review the saved details in your portal.',section='attendance' if label.startswith('Attendance') or label.startswith('Appointment') or label.startswith('Alternative attendance') else 'jobs')


def sync_closed_access(job):
    if not job.private_client_id or (not job.closed_at and job.status not in ('closed','cancelled')):return
    with transaction.atomic():
        client=PrivateClient.objects.select_for_update().select_related('user').get(pk=job.private_client_id)
        retire_links(client.links.filter(request=job))
        MailQueue.objects.filter(private_job=job,sent_at=None,retired_at=None).update(retired_at=timezone.now(),error_code='job_closed',body='[Closed job portal link removed]')
        if client.portal_active and not open_work(client):
            client.portal_active=False;client.save(update_fields=['portal_active'])
            User.objects.filter(pk=client.user_id).update(is_active=False,session_version=F('session_version')+1)
            retire_links(client.links.all())
            MailQueue.objects.create(recipient=client.email,subject='Sevlink — your work is closed',
                body=f'Hello {client.name},\n\nYour work is closed and your portal access has been deactivated. Your job, quotes, invoices and payment records remain with Sevlink. We can reactivate access with a fresh email link when you return.\n\nContact maintenance@sevlink.co.za for assistance.')


class PrivateRequestForm(forms.Form):
    name=forms.CharField(max_length=180)
    email=forms.EmailField(max_length=150)
    phone=forms.CharField(max_length=40)
    address=forms.CharField(max_length=400)
    title=forms.CharField(max_length=180)
    description=forms.CharField(max_length=2500)
    job_type=forms.ChoiceField(choices=[('quoted','Quotation'),('callout','Call-out')])
    limit=forms.DecimalField(max_digits=12,decimal_places=2,min_value=0.01,required=False)
    authorisation=forms.CharField(max_length=1000,required=False)

    def clean(self):
        data=super().clean()
        if data.get('job_type')=='callout' and (not data.get('limit') or not data.get('authorisation')):
            raise forms.ValidationError('Record the client’s call-out authorisation and maximum spending total.')
        return data


@api_access
@require_POST
def create_request(request):
    if not request.user.is_superuser:return JsonResponse({'error':'Sevlink Super Admin required.'},status=403)
    try:
        from .collaboration import request_key
        key=request_key(request)
        values=payload(request,('name','email','phone','address','title','description','job_type','limit','authorisation'))
        if any(k!='limit' and not isinstance(v,str) for k,v in values.items()):raise ValueError('Private-client details must be text.')
        form=PrivateRequestForm(values)
        if not form.is_valid():return JsonResponse({'error':'Check the private-client details.','fields':form.errors.get_json_data()},status=400)
        data=form.cleaned_data;email=data['email'].strip().lower()
        fingerprint=hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()
        with transaction.atomic():
            prior=MaintenanceRequest.objects.filter(submission_key=key).first()
            if prior:
                if prior.submission_fingerprint!=fingerprint or prior.reported_by_id!=request.user.pk:return JsonResponse({'error':'Submission key conflict.'},status=409)
                return JsonResponse(serialize(prior,request.user))
            client=PrivateClient.objects.select_for_update().filter(email__iexact=email).first()
            if not client:
                if User.objects.filter(email__iexact=email).exists():raise ValueError('This email already belongs to an agency or tenant login. Use a separate private-client email; accounts have not been merged.')
                agency=Agency.objects.create(kind='private',name='Private Client — '+data['name'],phone=data['phone'],area='Private client')
                user=User.objects.create_user(username=email,email=email,first_name=data['name'][:150],is_active=False)
                user.set_unusable_password();user.save(update_fields=['password'])
                Membership.objects.create(user=user,agency=agency,role=Membership.CLIENT)
                client=PrivateClient.objects.create(agency=agency,user=user,name=data['name'],email=email,phone=data['phone'],created_by=request.user)
            if client.name!=data['name'] or client.phone!=data['phone']:
                client.name=data['name'];client.phone=data['phone'];client.save(update_fields=['name','phone'])
            prop,_=Property.objects.get_or_create(agency=client.agency,address=data['address'],defaults={'name':'Private client property','access_responsibility':'sevlink'})
            callout=data['job_type']=='callout'
            job=MaintenanceRequest.objects.create(property=prop,private_client=client,reported_by=request.user,
                workflow_version=1,job_type=data['job_type'],jobs_payment_route='without_deposit' if callout else 'pending',
                title=data['title'],description=data['description'],category='General maintenance',status='reviewed',
                access_responsibility='sevlink',spending_limit=data['limit'] if callout else None,
                authorised_at=timezone.now() if callout else None,authorised_by=request.user if callout else None,
                submission_key=key,submission_fingerprint=fingerprint)
            if callout:
                from .numbering import approve_job_number
                from .models import WorkflowDecision
                approve_job_number(job)
                SchedulingArrangement.objects.create(request=job,actor=request.user,reason='Private call-out authorised: schedule immediately without a deposit.')
                WorkflowDecision.objects.create(request=job,actor=request.user,operation='private-callout',key=uuid.uuid4(),fingerprint=fingerprint,snapshot={'authorisation':data['authorisation'],'limit':str(data['limit'])})
                activate_or_notify(client,job)
            Audit.objects.create(agency=client.agency,actor=request.user,action='Private client request created',object_id=str(job.pk))
            return JsonResponse(serialize(job,request.user),status=201)
    except IntegrityError:return JsonResponse({'error':'The client record changed while saving. Refresh and try again.'},status=409)
    except ValueError as error:return JsonResponse({'error':str(error)},status=400)


def resolve_link(token,lock=False):
    qs=PrivateClientLink.objects.select_related('client__user','request__property','quotation__document')
    if lock:qs=qs.select_for_update(of=('self',))
    link=qs.filter(token_hash=digest(token)).first()
    if not link or link.revoked_at or link.expires_at<=timezone.now():return None
    if link.email.casefold()!=link.client.email.casefold() or link.email.casefold()!=link.client.user.email.casefold():return None
    if link.request.private_client_id!=link.client_id or link.request.closed_at or link.request.status in ('closed','cancelled'):return None
    if link.purpose=='quote':
        q=link.quotation
        if not q or q.request_id!=link.request_id or not q.document_id:return None
        if not link.used_at and (q.status!='sent' or q.version!=link.quote_version):return None
    elif link.used_at or not open_work(link.client):return None
    return link


@never_cache
@sensitive_post_parameters('new_password1','new_password2')
@require_http_methods(['GET','POST'])
def client_link(request,token):
    link=resolve_link(token)
    if not link:return render(request,'private_clients/unavailable.html',status=410)
    if link.purpose=='activate':
        if request.method=='POST' and limited('client-activation:'+request.META.get('REMOTE_ADDR',''),maximum=15):return HttpResponse('Please try again later.',status=429)
        form=SetPasswordForm(link.client.user,request.POST if request.method=='POST' else None)
        if request.method=='POST' and form.is_valid():
            with transaction.atomic():
                MaintenanceRequest.objects.select_for_update().get(pk=link.request_id)
                client=PrivateClient.objects.select_for_update().get(pk=link.client_id)
                link=resolve_link(token,lock=True)
                if not link:return render(request,'private_clients/unavailable.html',status=410)
                user=User.objects.select_for_update().get(pk=client.user_id)
                if not open_work(client):return render(request,'private_clients/unavailable.html',status=410)
                form=SetPasswordForm(user,request.POST)
                if not form.is_valid():return render(request,'private_clients/activate.html',{'form':form,'client':client})
                user=form.save(commit=False);user.is_active=True;user.session_version+=1;user.save(update_fields=['password','is_active','session_version'])
                client.portal_active=True;client.save(update_fields=['portal_active'])
                link.used_at=timezone.now();link.save(update_fields=['used_at'])
                retire_links(client.links.filter(purpose='activate',used_at=None))
                Audit.objects.create(agency=client.agency,actor=user,action='Private client portal activated',object_id=str(client.pk))
            login(request,user,backend='django.contrib.auth.backends.ModelBackend')
            return redirect(reverse('private_client_portal')+'?job='+str(link.request_id)+('&section=attendance' if link.request.job_type=='callout' else ''))
        response=render(request,'private_clients/activate.html',{'form':form,'client':link.client})
    else:
        error=''
        if request.method=='POST':
            if limited('private-quote:'+request.META.get('REMOTE_ADDR',''),maximum=30):return HttpResponse('Please try again later.',status=429)
            decision=request.POST.get('decision');reason=request.POST.get('reason','').strip()
            if decision not in ('approved','rejected') or len(reason)>1000:error='Choose Accept or Decline; keep comments within 1,000 characters.'
            elif not link.used_at:
                with transaction.atomic():
                    job=MaintenanceRequest.objects.select_for_update().get(pk=link.request_id)
                    q=JobQuotation.objects.select_for_update().get(pk=link.quotation_id)
                    link=resolve_link(token,lock=True)
                    if not link:return render(request,'private_clients/unavailable.html',status=410)
                    if not link.used_at:
                        if q.status!='sent' or q.version!=link.quote_version:return render(request,'private_clients/unavailable.html',status=410)
                        q.status=decision;q.decided_by=link.client.user;q.decided_at=timezone.now();q.decision_reason=reason;q.decision_key=uuid.uuid4();q.version+=1;q.save()
                        if decision=='approved':
                            from .numbering import approve_job_number
                            approve_job_number(job)
                        from .quotations import action
                        action(q,link.client.user,decision,q.decision_key,digest(str(link.pk)+decision),reason)
                        link.used_at=timezone.now();link.save(update_fields=['used_at'])
                        Audit.objects.create(agency=link.client.agency,actor=link.client.user,action='Private quote '+decision,object_id=str(q.pk))
                link=resolve_link(token)
        response=render(request,'private_clients/review.html',{'link':link,'token':token,'error':error})
    response['Referrer-Policy']='same-origin'
    response['X-Robots-Tag']='noindex, nofollow'
    return response


@never_cache
@require_GET
def client_pdf(request,token):
    link=resolve_link(token)
    if not link or link.purpose!='quote':return HttpResponse('Quotation link unavailable.',status=410)
    from .attachments import file_response
    response=file_response(link.quotation.document)
    if request.GET.get('download')!='1':response['Content-Disposition']=content_disposition_header(False,link.quotation.document.filename)
    response['Referrer-Policy']='same-origin';response['X-Robots-Tag']='noindex, nofollow';response['X-Frame-Options']='SAMEORIGIN'
    return response


@login_required
@never_cache
@ensure_csrf_cookie
def portal(request):
    from .maintenance import access
    if access(request.user)[0]!=Membership.CLIENT:return HttpResponse('Private-client access required.',status=403)
    return render(request,'private_clients/portal.html',{'client':request.user.private_client})


def validate_delivery(item):
    link=PrivateClientLink.objects.select_related('client__user','request','quotation').filter(message=item).first()
    if link and (link.used_at or link.revoked_at or link.expires_at<=timezone.now() or link.email.casefold()!=link.client.email.casefold() or link.request.closed_at or link.request.status in ('closed','cancelled') or (link.purpose=='quote' and (link.quotation.status!='sent' or link.quote_version!=link.quotation.version))):
        from .completion_delivery import DeliveryBlocked
        raise DeliveryBlocked('Client link is no longer valid.')
