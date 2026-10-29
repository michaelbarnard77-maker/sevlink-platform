"""Explicit Super Admin controls; no changes occur during a removal preview."""
import hashlib
import json
import secrets
import uuid
from django.apps import apps
from django.core import signing
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET,require_POST,require_http_methods
from . import models as m, attachments
from .maintenance import api_access,payload,serialize,requests_for
from .collaboration import request_key
from .events import record
from .commercial import text
from .workflow import STAGES


@api_access
@require_POST
def move_job(request,job_id):
    if not request.user.is_superuser:return JsonResponse({'error':'Sevlink Super Admin access required.'},status=403)
    try:
        values=payload(request,('version','stage','reason'))
        key=request_key(request);reason=text(values.get('reason'),1000)
        target=values.get('stage')
        if target not in dict(STAGES) or type(values.get('version')) is not int:raise ValueError('Choose a job stage and current version.')
        fingerprint=hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()
        with transaction.atomic():
            job=get_object_or_404(m.MaintenanceRequest.objects.select_for_update(),pk=job_id)
            old=m.WorkflowDecision.objects.filter(key=key).first()
            if old:
                if old.operation!='manual-stage' or old.request_id!=job.pk or old.actor_id!=request.user.pk or old.fingerprint!=fingerprint:return JsonResponse({'error':'Submission key conflict.'},status=409)
                return JsonResponse(serialize(job,request.user))
            if job.version!=values['version']:return JsonResponse({'error':'Job changed. Refresh before moving it.'},status=409)
            previous=job.status
            job.status={'new':'awaiting_review','quoting':'reviewed','approval':'reviewed','deposit':'reviewed','ready':'reviewed','booked':'scheduled','underway':'in_progress','invoice':'completed','payment':'completed','closed':'closed'}[target]
            job.closed_at=timezone.now() if target=='closed' else None
            job.version+=1;job.save(update_fields=['status','closed_at','version','updated_at'])
            decision=m.WorkflowDecision.objects.create(request=job,actor=request.user,operation='manual-stage',key=key,fingerprint=fingerprint,
                snapshot=dict(stage=target,reason=reason,previous_status=previous,status=job.status,version=job.version))
            m.MaintenanceStatusEvent.objects.create(request=job,actor=request.user,status=job.status)
            event=record(job,request.user,'workflow_event','manual-move:'+str(key),
                {'action':'Job moved manually to '+dict(STAGES)[target],'decision_id':str(decision.pk)},private=True)
            from .workflow import notify,participants
            notify(event,participants(job))
        return JsonResponse(serialize(job,request.user))
    except ValueError as error:return JsonResponse({'error':str(error)},status=400)


def roots(kind,identifier):
    model={'agency':m.Agency,'property':m.Property,'tenant':m.Tenancy}.get(kind)
    if not model:raise ValueError('Unknown removal type.')
    root=get_object_or_404(model,pk=identifier)
    agency=root if kind=='agency' else root.agency if kind=='property' else root.property.agency
    props=m.Property.objects.filter(agency=agency) if kind=='agency' else m.Property.objects.filter(pk=root.pk) if kind=='property' else m.Property.objects.none()
    users=[]
    if kind=='agency':
        if m.Membership.objects.filter(agency=agency,user__is_staff=True,user__is_superuser=False).exists():
            raise ValueError('This agency has a protected staff account association. Review its account access before removing the agency.')
        users=list(m.User.objects.filter(membership__agency=agency,is_staff=False,is_superuser=False))
    elif kind=='tenant' and root.user_id:
        user=root.user
        if user.is_staff or user.is_superuser or not m.Membership.objects.filter(user=user,role='tenant',agency=agency).exists():
            raise ValueError('This is a protected account, not a removable tenant account.')
        users=[user]
    elif kind=='property':
        ids=m.Tenancy.objects.filter(property=root,user__membership__role='tenant',user__membership__agency=agency).values_list('user_id',flat=True)
        users=[u for u in m.User.objects.filter(pk__in=ids,is_staff=False,is_superuser=False)
               if not m.Tenancy.objects.filter(user=u).exclude(property=root).exists()]
    return root,agency,set(props.values_list('pk',flat=True)),users


def graph_for(root):
    """Follow incoming FK/M2M references, never forward to staff, suppliers or locations."""
    found={type(root):{root.pk}}
    models=list(apps.get_models(include_auto_created=True))
    changed=True
    while changed:
        changed=False
        for model in models:
            for field in model._meta.local_fields:
                if not field.is_relation or not field.many_to_one and not field.one_to_one:continue
                parent=field.remote_field.model
                if parent not in found:continue
                ids=set(model._base_manager.filter(**{field.attname+'__in':found[parent]}).values_list('pk',flat=True))
                new=ids-found.get(model,set())
                if new:found.setdefault(model,set()).update(new);changed=True
        # The completion message owns its MIME payload and attempts, not its parent job.
        if m.CompletionPackage in found:
            ids=set(m.CompletionPackage.objects.filter(pk__in=found[m.CompletionPackage]).values_list('message_id',flat=True))
            if ids-found.get(m.MailQueue,set()):found.setdefault(m.MailQueue,set()).update(ids);changed=True
        if m.JobQuotation in found:
            quotes=m.JobQuotation.objects.filter(pk__in=found[m.JobQuotation])
            series=set(quotes.values_list('series_id',flat=True))
            series-=set(m.JobQuotation.objects.filter(series_id__in=series).exclude(pk__in=found[m.JobQuotation]).values_list('series_id',flat=True))
            ids=set(m.QuotationReferenceReservation.objects.filter(series_id__in=series).values_list('pk',flat=True))
            if ids-found.get(m.QuotationReferenceReservation,set()):found.setdefault(m.QuotationReferenceReservation,set()).update(ids);changed=True
        # Older operational audit rows store UUID references/appointment IDs without an FK.
        object_ids=[str(pk) for ids in found.values() for pk in ids if isinstance(pk,uuid.UUID)]
        ids=set(m.Audit.objects.filter(object_id__in=object_ids).values_list('pk',flat=True))
        if ids-found.get(m.Audit,set()):found.setdefault(m.Audit,set()).update(ids);changed=True
        for key,model_name in [('appointment','teamappointment'),('assignment','jobassignment'),('review','assignmentreview')]:
            linked=next((ids for model,ids in found.items() if model._meta.model_name==model_name),set())
            if linked:
                ids=set(m.SupplierActivity.objects.filter(**{'details__'+key+'__in':list(linked)}).values_list('pk',flat=True))
                if ids-found.get(m.SupplierActivity,set()):found.setdefault(m.SupplierActivity,set()).update(ids);changed=True
        if sum(map(len,found.values()))>20000:raise ValueError('This removal is too large for the interactive control. Use a reviewed batch removal.')
    return found


def removal_plan(kind,identifier):
    root,agency,props,users=roots(kind,identifier)
    if kind=='tenant':graph={}
    else:
        graph=graph_for(root)
        # A cross-property/cross-agency link must never expand the user's chosen scope.
        if set(m.MaintenanceRequest.objects.filter(pk__in=graph.get(m.MaintenanceRequest,set())).values_list('property_id',flat=True))-props:
            raise ValueError('Linked jobs extend outside this selection. Remove or review those links first.')
        for model,ids in graph.items():
            for field in model._meta.local_fields:
                if not field.is_relation or not (field.many_to_one or field.one_to_one):continue
                parent=field.remote_field.model;lookup=None;allowed=None
                if parent is m.Property:lookup=field.name+'_id';allowed=props
                elif parent is m.Agency:lookup=field.name+'_id';allowed={agency.pk}
                elif parent is m.MaintenanceRequest:lookup=field.name+'__property_id';allowed=props
                elif any(f.name=='request' and f.is_relation and f.remote_field.model is m.MaintenanceRequest for f in parent._meta.local_fields):
                    lookup=field.name+'__request__property_id';allowed=props
                if lookup and model._base_manager.filter(pk__in=ids,**{field.name+'__isnull':False}).exclude(**{lookup+'__in':allowed}).exists():
                    raise ValueError('Linked records extend outside this property or agency. Review those links before removing it.')
        if m.User in graph or m.Subcontractor in graph or m.Agency in graph and kind!='agency':
            raise ValueError('The removal would affect protected or unrelated records.')
    counts={model._meta.label_lower:len(ids) for model,ids in graph.items()}
    counts['accounts_cleared']=len(users)
    fingerprint=[]
    for model,ids in sorted(graph.items(),key=lambda pair:pair[0]._meta.label_lower):
        fingerprint.append([model._meta.label_lower,list(model._base_manager.filter(pk__in=ids).order_by('pk').values())])
    fingerprint += [['root',kind,str(root.pk),str(root)],['accounts',[(u.pk,u.email,u.session_version) for u in users]]]
    if kind=='tenant':fingerprint.append(list(m.Tenancy.objects.filter(pk=root.pk).values()))
    digest=hashlib.sha256(json.dumps(fingerprint,sort_keys=True,default=str).encode()).hexdigest()
    label=root.name if kind in ('agency','tenant') else root.address
    return dict(root=root,agency=agency,users=users,graph=graph,counts=counts,digest=digest,label=label)


def clear_accounts(users,tenancy=None):
    """Keep an unidentifiable actor stub so job/payment history is never reassigned."""
    ids=[]
    for user in users:
        ids.append(user.pk);old_email=user.email
        anon='removed-'+uuid.uuid4().hex
        user.username=anon;user.email=anon+'@removed.invalid';user.first_name='Removed account';user.last_name=''
        user.is_active=False;user.last_login=None;user.session_version+=1;user.set_unusable_password();user.save()
        m.Tenancy.objects.filter(user=user).update(name='Removed tenant',email=user.email,phone='',active=False)
        for invite in m.Invitation.objects.filter(email__iexact=old_email):
            invite.name='Removed account';invite.email=user.email;invite.token_hash=secrets.token_hex(32);invite.revoked_at=timezone.now();invite.save()
        # Queued account messages may contain links/contact information for this account.
        messages=m.MailQueue.objects.filter(recipient__iexact=old_email)
        # Preserve packages referenced by retained job history, but erase their queued message content.
        messages.update(recipient=user.email,subject='Removed account',body='',retired_at=timezone.now())
        m.JobActivity.objects.filter(actor=user)._update([(m.JobActivity._meta.get_field('actor_name'),None,'Removed account')])
        from django_otp.plugins.otp_totp.models import TOTPDevice
        TOTPDevice.objects.filter(user=user).delete()
    if tenancy is not None and not users:
        old_email=tenancy.email
        tenancy.name='Removed tenant';tenancy.email='removed-'+uuid.uuid4().hex+'@removed.invalid';tenancy.phone='';tenancy.active=False;tenancy.save()
        if not m.Tenancy.objects.filter(email__iexact=old_email,active=True).exclude(pk=tenancy.pk).exists():
            m.MailQueue.objects.filter(recipient__iexact=old_email).update(recipient=tenancy.email,subject='Removed tenant',body='',retired_at=timezone.now())
        for invite in m.Invitation.objects.filter(tenancy=tenancy):
            invite.name='Removed tenant';invite.email=tenancy.email;invite.token_hash=secrets.token_hex(32);invite.revoked_at=timezone.now();invite.save()
    if ids:
        from django.contrib.sessions.models import Session
        for session in Session.objects.iterator():
            if str(session.get_decoded().get('_auth_user_id')) in {str(v) for v in ids}:session.delete()


def cleanup_receipt(receipt):
    pending=[]
    for key in receipt.pending_files:
        try:attachments.storage().delete(key)
        except Exception:pending.append(key)
    receipt.pending_files=pending;receipt.save(update_fields=['pending_files'])


def display_counts(counts):
    labels={'portal.agency':'Agencies','portal.property':'Properties','portal.tenancy':'Tenant links',
        'portal.maintenancerequest':'Repair jobs','portal.jobquotation':'Quotes','portal.jobinvoice':'Invoices',
        'portal.maintenanceattachment':'Documents and photos','portal.invoicepayment':'Recorded payments',
        'portal.operationsnotification':'Operations notifications','accounts_cleared':'Accounts cleared','portal.teamappointment':'Calendar appointments','portal.jobassignment':'Subcontractor assignments','portal.attendancerequest':'Attendance requests','portal.mailqueue':'Saved message records'}
    result={label:counts[k] for k,label in labels.items() if counts.get(k)}
    remainder=sum(v for k,v in counts.items() if k not in labels)
    if remainder:result['Related history and notification records']=remainder
    return result


@api_access
@require_http_methods(['GET','POST'])
def remove(request,kind,identifier):
    if not request.user.is_superuser:return JsonResponse({'error':'Sevlink Super Admin access required.'},status=403)
    try:
        with transaction.atomic():
            plan=removal_plan(kind,identifier)
            if request.method=='GET':
                token=signing.dumps(dict(kind=kind,id=str(identifier),digest=plan['digest'],actor=request.user.pk),salt='removal-preview')
                return JsonResponse(dict(name=plan['label'],kind=kind,counts=display_counts(plan['counts']),token=token,
                    keeps_jobs=kind=='tenant',note='Tenant login and structured contact details will be removed. Original job text, photos, quotes and invoices remain as history.' if kind=='tenant' else 'Permanently removes the selected record and the linked jobs, documents, payments, calendar entries and notifications shown below from the live portal. Shared accounts, existing backups and previously delivered emails are retained.'))
            values=payload(request,('token','confirmation'))
            if values.get('confirmation')!='REMOVE':raise ValueError('Type REMOVE to confirm.')
            try:preview=signing.loads(values.get('token',''),salt='removal-preview',max_age=600)
            except signing.BadSignature:raise ValueError('Removal preview expired. Open it again.')
            if preview!=dict(kind=kind,id=str(identifier),digest=plan['digest'],actor=request.user.pk):
                return JsonResponse({'error':'Records changed. Review a fresh removal preview.'},status=409)
            type(plan['root'])._base_manager.select_for_update().get(pk=plan['root'].pk)
            list(m.User.objects.filter(pk__in=[u.pk for u in plan['users']]).select_for_update())
            for model,ids in sorted(plan['graph'].items(),key=lambda pair:pair[0]._meta.label_lower):
                list(model._base_manager.filter(pk__in=ids).select_for_update().values_list('pk',flat=True))
            if removal_plan(kind,identifier)['digest']!=preview['digest']:
                return JsonResponse({'error':'Records changed during review. Open a fresh preview.'},status=409)
            keys=list(m.MaintenanceAttachment.objects.filter(pk__in=plan['graph'].get(m.MaintenanceAttachment,set())).values_list('storage_key',flat=True))
            clear_accounts(plan['users'],plan['root'] if kind=='tenant' else None)
            # Explicit removal is the only path that bypasses model PROTECT/append-only hooks.
            # All incoming references are included; DB FK constraints remain enabled throughout.
            for model,ids in plan['graph'].items():model._base_manager.filter(pk__in=ids)._raw_delete('default')
            receipt=m.RemovalReceipt.objects.create(actor=request.user,kind=kind,counts=plan['counts'],pending_files=keys)
            transaction.on_commit(lambda:cleanup_receipt(receipt))
        receipt.refresh_from_db()
        return JsonResponse(dict(removed=True,kept_jobs=kind=='tenant',cleanup_pending=bool(receipt.pending_files),receipt=str(receipt.pk)))
    except ValueError as error:return JsonResponse({'error':str(error)},status=400)


@api_access
@require_POST
def retry_cleanup(request,receipt_id):
    if not request.user.is_superuser:return JsonResponse({'error':'Sevlink Super Admin access required.'},status=403)
    receipt=get_object_or_404(m.RemovalReceipt,pk=receipt_id)
    cleanup_receipt(receipt)
    return JsonResponse({'cleanup_pending':bool(receipt.pending_files)})
