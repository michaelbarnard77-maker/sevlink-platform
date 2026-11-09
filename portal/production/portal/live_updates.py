"""Small, authenticated change marker; all job queries retain the caller's scope."""
import hashlib
import json
from django.db.models import Count, Max
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .maintenance import api_access, requests_for
from . import models

@api_access
@require_GET
def revision(request):
    jobs = requests_for(request.user).order_by()
    parts = [list(jobs.values_list('pk','version','updated_at').order_by('pk'))]
    parts.append(list(models.JobQuotation.objects.filter(request__in=jobs).order_by('pk').values_list('pk','version','status')))
    parts.append(list(models.JobInvoice.objects.filter(request__in=jobs).order_by('pk').values_list('pk','version','payment_status','document_status','visibility')))
    for model in (models.JobActivity, models.JobComment, models.MaintenanceAttachment, models.WorkflowDecision, models.CompletionRecord):
        parts.append(model.objects.filter(request__in=jobs).aggregate(count=Count('pk'),latest=Max('created_at')))
    parts.append(list(models.JobActionRequest.objects.filter(request__in=jobs).order_by('pk').values_list('pk','resolved_at')))
    parts.append(list(models.AdditionalAuthorisation.objects.filter(request__in=jobs).order_by('pk').values_list('pk','status')))
    parts.append(list(models.AttendanceRequest.objects.filter(request__in=jobs).order_by('pk').values_list('pk','status','preference','requested_date','requested_window','agreed_date','agreed_window','appointment_id')))
    parts.append(list(models.TeamAppointment.objects.filter(assignment__request__in=jobs).order_by('pk').values_list('pk','version','progress_status','cancelled_at','starts_at','ends_at')))
    parts.append(list(models.UserJobNotification.objects.filter(user=request.user,event__request__in=jobs).order_by('pk').values_list('pk','read_at')))
    if request.user.is_superuser:
        parts.append(list(models.WebsiteEnquiry.objects.order_by('pk').values_list('pk','status')))
    marker = hashlib.sha256(json.dumps(parts,default=str,separators=(',',':')).encode()).hexdigest()
    response = JsonResponse({'revision':marker})
    response['Cache-Control'] = 'no-store'
    return response
