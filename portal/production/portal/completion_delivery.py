"""Private completion-report PDFs and one combined PM email; never sends inline."""
from io import BytesIO
from itertools import zip_longest
import textwrap
from pathlib import Path
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import EmailMessage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_GET
from PIL import Image, ImageDraw, ImageFont, ImageOps
from . import attachments
from .models import CompletionPackage, MailQueue, Membership, OperationsFeedback
from .maintenance import api_access, requests_for


class DeliveryBlocked(ValueError):
    pass


def eligible_recipient(job):
    if job.private_client_id:return job.private_client.user if job.private_client.user.email.casefold()==job.private_client.email.casefold() else None
    pm=job.property.manager
    if not pm or not pm.is_active or not pm.email:return None
    if not Membership.objects.filter(user=pm,agency=job.property.agency,role__in=['pm','admin']).exists():return None
    return pm


def build_report(job,completion):
    """Branded A4 report with the accepted description and paired evidence."""
    pages=[];size=(1240,1754)
    ink='#173b50';teal='#25858c';muted='#617986'
    fonts=Path(__file__).parent/'email_assets'
    font=ImageFont.truetype(str(fonts/'report-sans.ttf'),25)
    small=ImageFont.truetype(str(fonts/'report-sans.ttf'),21)
    title=ImageFont.truetype(str(fonts/'report-sans-bold.ttf'),36)
    def wrap(value):
        width=73
        while width>1:
            lines=textwrap.wrap(value,width=width) or ['']
            if all(font.getlength(line)<=1100 for line in lines):return lines
            width-=1
        return list(value)
    def page(label):
        image=Image.new('RGB',size,'#f1f6f9');draw=ImageDraw.Draw(image)
        draw.rounded_rectangle((35,35,1205,1698),radius=24,fill='white')
        draw.rounded_rectangle((70,55,1170,65),radius=5,fill=teal)
        logo_path=settings.BASE_DIR/'static/landing/assets/sevlink-logo.png'
        if logo_path.exists():
            with Image.open(logo_path) as original:
                logo=original.convert('RGBA');logo.thumbnail((200,105));image.paste(logo,(70,85),logo)
        else:draw.text((70,100),'SEVLINK',fill=ink,font=title)
        draw.text((670,100),'COMPLETION REPORT',fill=ink,font=font)
        draw.text((670,145),job.reference,fill=teal,font=font)
        draw.line((70,215,1170,215),fill='#dce8ee',width=2)
        draw.text((70,240),label,fill=teal,font=font)
        pages.append(image);return image,draw
    image,draw=page('YOUR PROPERTY. OUR PRIORITY.');y=305
    from django.utils import timezone
    details=[('PROPERTY',job.property.address),('JOB',job.title),('REPORT DATE',timezone.localtime(completion.created_at).strftime('%d %B %Y')),('WORK COMPLETED',completion.report)]
    if completion.before_unavailable:details.append(('BEFORE PHOTOGRAPHS',completion.exception_reason))
    for heading,value in details:
        if y>1450:image,draw=page('WORK COMPLETED — CONTINUED');y=305
        draw.text((70,y),heading,fill=teal,font=small);y+=42
        for line in value.splitlines():
            for wrapped in wrap(line):
                if y>1550:image,draw=page('WORK COMPLETED — CONTINUED');y=305
                draw.text((70,y),wrapped,fill=ink,font=font);y+=38
        y+=30
    docs=completion.documents.filter(visibility__in=['shared','agency']).exclude(comment__visibility='internal')
    before=list(docs.filter(purpose='completion_before',content_type__startswith='image/'))
    after=list(docs.filter(purpose='completion_after',content_type__startswith='image/'))
    if len(before)+len(after)>20:raise ValueError('A completion PDF supports up to 20 report photographs.')
    for left,right in zip_longest(before,after):
        image,draw=page('BEFORE & AFTER PHOTOGRAPHS')
        pictures=[]
        for document in (left,right):
            if document:
                with attachments.storage().open(document.storage_key,'rb') as handle:
                    with Image.open(handle) as original:pictures.append(ImageOps.exif_transpose(original).convert('RGB'))
            else:pictures.append(None)
        landscape=all(photo is None or photo.width>photo.height for photo in pictures)
        boxes=[(70,300,1170,895),(70,935,1170,1530)] if landscape else [(70,300,600,1550),(640,300,1170,1550)]
        for photo,document,label,box in zip(pictures,(left,right),('BEFORE WORK','AFTER WORK'),boxes):
            x,y,right_edge,bottom=box;width=right_edge-x
            draw.rounded_rectangle(box,radius=16,fill='#f1f6f9',outline='#dce8ee',width=2)
            draw.text((x+20,y+25),label,fill=teal,font=font)
            if photo:
                photo.thumbnail((width-40,bottom-y-150))
                image.paste(photo,(x+(width-photo.width)//2,y+80+(bottom-y-150-photo.height)//2))
                photo.close()
                draw.text((x+20,bottom-45),document.filename[:40],fill=muted,font=small)
            else:draw.text((x+20,y+110),'No photograph supplied.',fill=muted,font=small)
    for number,image in enumerate(pages,1):
        draw=ImageDraw.Draw(image);draw.line((70,1615,1170,1615),fill='#dce8ee',width=2)
        draw.text((70,1635),'maintenance@sevlink.co.za  |  081 028 5034',fill=muted,font=small)
        draw.text((1170,1635),f'{number} / {len(pages)}',fill=muted,font=small,anchor='ra')
    output=BytesIO()
    pages[0].save(output,format='PDF',save_all=True,append_images=pages[1:],resolution=150,quality=82,
        title='Sevlink '+job.reference+' completion report',author='Sevlink')
    for image in pages:image.close()
    return output.getvalue()


def ensure_report(job,completion,actor,keys):
    report=completion.documents.filter(purpose='completion_report').order_by('-created_at','-pk').first()
    if report:return report
    raw=build_report(job,completion)
    prepared=attachments.prepare([SimpleUploadedFile('Sevlink-'+job.reference+'-completion-report.pdf',raw,content_type='application/pdf')])
    report=attachments.save_files(job,actor,prepared,keys,visibility='agency',purpose='completion_report')[0]
    completion.documents.add(report)
    return report


def maybe_queue(job,actor):
    """Caller holds the job lock/transaction. No completion or invoice => no mail."""
    if not transaction.get_connection().in_atomic_block:raise RuntimeError('Completion delivery must share the saved transaction.')
    if job.status not in ('completed','closed'):return None
    from .workflow import completion_valid,effective_quotes
    if not completion_valid(job):return None
    recipient=eligible_recipient(job)
    if not recipient:return None
    invoices=job.invoices.filter(visibility='shared',subcontractor=None,document_status='active',reconciliation_required=False)
    invoice=invoices.filter(purpose='final').order_by('-created_at').first()
    if invoice is None:
        # A full original company invoice can carry deposit and final receipts.
        from django.db.models import Sum
        approved=effective_quotes(job).aggregate(amount=Sum('amount'))['amount']
        if approved:invoice=invoices.filter(amount=approved,purpose='deposit').order_by('-created_at').first()
    if not invoice:return None
    existing=CompletionPackage.objects.filter(invoice=invoice).first()
    if existing:return existing
    completion=job.completion_records.order_by('-created_at','-pk').first();keys=[]
    try:
        report=ensure_report(job,completion,actor,keys)
        message=MailQueue.objects.create(recipient=recipient.email,subject='Sevlink '+job.reference+' — completion report and final invoice',
            body='\n'.join(['Hi '+(recipient.first_name or 'Property Manager')+',','',
                'The completed Before & After Report and original final invoice are attached.',
                'Job: '+job.reference,'Property: '+job.property.address,'Invoice: '+invoice.number,
                'Please review the attached invoice for its payment terms.','',
                'Kind regards,','Sevlink Property Maintenance']))
        return CompletionPackage.objects.create(invoice=invoice,completion=completion,report_document=report,recipient=recipient,message=message)
    except Exception:
        attachments.cleanup(keys);raise


def attach_documents(item,message):
    """Recheck current document/recipient access before attaching any private bytes."""
    try:package=item.completion_package
    except ObjectDoesNotExist:return False
    invoice=package.invoice;job=invoice.request;recipient=eligible_recipient(job)
    if OperationsFeedback.objects.filter(notification__recipient=item.recipient,kind__in=['bounce','complaint'],resolution__isnull=True).exists():raise DeliveryBlocked('Recipient delivery is suppressed.')
    latest=job.completion_records.order_by('-created_at','-pk').first()
    if (not latest or latest.pk!=package.completion_id or not recipient or recipient.pk!=package.recipient_id or recipient.email!=item.recipient or
        invoice.visibility!='shared' or invoice.subcontractor_id or invoice.document_status!='active' or invoice.reconciliation_required or
        job.status not in ('completed','closed')):raise DeliveryBlocked('Completion delivery is no longer authorised.')
    for document,name in [(package.report_document,'Sevlink-'+job.reference+'-completion-report.pdf'),(invoice.document,invoice.number+'.pdf')]:
        with attachments.storage().open(document.storage_key,'rb') as handle:message.attach(name,handle.read(),'application/pdf')
    return True


@api_access
@require_GET
def status(request,job_id):
    job=get_object_or_404(requests_for(request.user),pk=job_id)
    if not request.user.is_superuser:raise Http404
    package=CompletionPackage.objects.filter(invoice__request=job).select_related('message','report_document').order_by('-created_at').first()
    if not package:
        completion=job.completion_records.order_by('-created_at','-pk').first()
        report=completion.documents.filter(purpose='completion_report').order_by('-created_at','-pk').first() if completion else None
        return JsonResponse({'queued':False,'report_ready':bool(report),'report_url':reverse('maintenance_attachment_download',args=[job.pk,report.pk]) if report else None})
    state='sent' if package.message.sent_at else 'blocked' if package.message.retired_at else 'failed' if package.message.attempts>=5 else 'preview' if package.message.error_code=='preview_only' else 'queued'
    return JsonResponse({'queued':True,'state':state,'report_url':reverse('maintenance_attachment_download',args=[job.pk,package.report_document_id]),'invoice_number':package.invoice.number,'live_enabled':bool(settings.SMTP_DELIVERY_ENABLED and settings.OPERATIONS_LIVE_DELIVERY_ENABLED)})


from django.views.decorators.http import require_POST
from django.db import transaction
from .commercial import text
from .collaboration import request_key
from .quotations import digest
from .models import CompletionRecord, MaintenanceRequest, WorkflowDecision


@api_access
@require_POST
def upload_completed_report(request,job_id):
    """Save both photo sets after work, then accept one completed report atomically."""
    if not request.user.is_superuser:return JsonResponse({'error':'Sevlink Operations access required.'},status=403)
    keys=[]
    try:
        key=request_key(request);report=text(request.POST.get('report'),5000)
        if getattr(request,'attachment_upload_rejected',False):raise ValueError('Select at most five before and five after photos, up to 5 MB each.')
        if len(request.FILES.getlist('before_photos'))>5 or len(request.FILES.getlist('after_photos'))>5:raise ValueError('Select up to five photos in each set.')
        exception=request.POST.get('before_unavailable')=='true';reason=text(request.POST.get('exception_reason',''),1000,False)
        version=int(request.POST.get('version',''))
        before=attachments.prepare(request.FILES.getlist('before_photos'));after=attachments.prepare(request.FILES.getlist('after_photos'))
        if any(not item['content_type'].startswith('image/') for item in before+after):raise ValueError('Before and after uploads must be photographs.')
        import hashlib
        mark_completed=request.POST.get('mark_completed')=='true'
        fingerprint=digest({'report':report,'exception':exception,'reason':reason,'mark_completed':mark_completed,'before':[(p['filename'],hashlib.sha256(p['data']).hexdigest()) for p in before],'after':[(p['filename'],hashlib.sha256(p['data']).hexdigest()) for p in after]})
        with transaction.atomic():
            job=get_object_or_404(requests_for(request.user).select_for_update(of=('self',)),pk=job_id)
            prior=WorkflowDecision.objects.filter(key=key).first()
            if prior:
                if prior.request_id!=job.pk or prior.actor_id!=request.user.pk or prior.fingerprint!=fingerprint:return JsonResponse({'error':'Submission key conflict.'},status=409)
                return JsonResponse({'saved':True})
            if job.closed_at:raise ValueError('Closed job documentation is retained; new uploads are blocked.')
            if version!=job.version:return JsonResponse({'error':'Job changed. Refresh before uploading.'},status=409)
            if exception and not reason:raise ValueError('Record why before photographs are unavailable.')
            current=job.attachments.filter(purpose__in=['completion_before','completion_after'])
            if current.count()+len(before)+len(after)>20:raise ValueError('The report supports up to 20 before/after photos in total.')
            if not after and not current.filter(purpose='completion_after').exists():raise ValueError('Upload the after-work photographs.')
            if not before and not current.filter(purpose='completion_before').exists() and not exception:raise ValueError('Upload before-work photographs or record why they are unavailable.')
            attachments.save_files(job,request.user,before,keys,purpose='completion_before')
            attachments.save_files(job,request.user,after,keys,purpose='completion_after')
            completion=CompletionRecord.objects.create(request=job,recorded_by=request.user,report=report,before_unavailable=exception,exception_reason=reason)
            completion.documents.set(job.attachments.filter(purpose__in=['completion_before','completion_after']))
            ensure_report(job,completion,request.user,keys)
            job.version+=1;job.save(update_fields=['version'])
            decision=WorkflowDecision.objects.create(request=job,actor=request.user,operation='completion',key=key,fingerprint=fingerprint,snapshot={'completion':completion.pk})
            from .workflow import attention_notifications
            attention_notifications(job,request.user,'Completion report and photographs available',str(key),tenant=True)
            if mark_completed and job.status!='completed':
                from .maintenance import update_status
                response=update_status(request.user,job,{'status':'completed','version':job.version})
                if response.status_code>=400:
                    import json
                    raise ValueError(json.loads(response.content).get('error','Work cannot yet be marked Completed.'))
                job.refresh_from_db()
            maybe_queue(job,request.user)
        return JsonResponse({'saved':True},status=201)
    except (ValueError,attachments.UploadStorageError) as error:
        attachments.cleanup(keys)
        return JsonResponse({'error':str(error) if isinstance(error,ValueError) else 'Private storage is unavailable.'},status=400)
    except Exception:
        attachments.cleanup(keys);raise
