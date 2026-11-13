"""Private-client section badges reuse recipient read state and existing job permissions."""
import uuid
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from .maintenance import api_access,access,requests_for,serialize,payload
from .models import Membership,UserJobNotification

SECTIONS={'jobs':('overview','activity','reports'),'quotes':('quotes',),'invoices':('invoices',),'attendance':('attendance',),'comments':('comments',)}


def summary(user):
    counts={key:0 for key in SECTIONS};jobs={}
    for job in requests_for(user):
        attention=serialize(job,user)['tab_attention']
        badges={key:sum(attention['counts'].get(tab,0) for tab in tabs) for key,tabs in SECTIONS.items()}
        jobs[str(job.pk)]={'reference':job.reference,'counts':badges}
        for key,value in badges.items():counts[key]+=value
    return {'counts':counts,'jobs':jobs}


@api_access
@require_http_methods(['GET','POST'])
def notifications(request):
    if access(request.user)[0]!=Membership.CLIENT:
        return JsonResponse({'error':'Private-client access required.'},status=403)
    if request.method=='POST':
        try:
            values=payload(request,('job','section','notifications'))
            job_id=uuid.UUID(values.get('job',''))
            section=values.get('section')
            ids=values.get('notifications')
            if section not in SECTIONS or not isinstance(ids,list) or len(ids)>1000 or any(type(n)is not int or n<1 for n in ids):raise ValueError('Invalid notification selection.')
        except (ValueError,TypeError,AttributeError) as error:
            return JsonResponse({'error':'Invalid notification selection.'},status=400)
        job=get_object_or_404(requests_for(request.user),pk=job_id)
        attention=serialize(job,request.user)['tab_attention']
        allowed={n for tab in SECTIONS[section] for n in attention['unread'].get(tab,[])}
        UserJobNotification.objects.filter(user=request.user,event__request=job,pk__in=allowed.intersection(ids),read_at=None).update(read_at=timezone.now())
    return JsonResponse(summary(request.user))
