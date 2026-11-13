"""Staff enquiry workspace. Per-person read receipts are separate from follow-up status."""
import uuid
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET,require_POST,require_http_methods
from .models import WebsiteEnquiry,WebsiteEnquiryReadReceipt
from .staff_access import staff_only,can_schedule
from .maintenance import payload


def unread(user):
    return WebsiteEnquiry.objects.exclude(read_receipts__user=user)


@staff_only(can_schedule)
@require_GET
def count(request):
    return JsonResponse({'unread':unread(request.user).count()})


@staff_only(can_schedule)
@require_http_methods(['GET','POST'])
def collection(request):
    if request.method=='POST':
        try:
            data=payload(request,('id','status'))
            if data.get('status') not in dict(WebsiteEnquiry._meta.get_field('status').choices):raise ValueError('Choose a valid status.')
            identifier=uuid.UUID(data.get('id',''))
        except (ValueError,TypeError,AttributeError) as error:return JsonResponse({'error':'Invalid enquiry or status.'},status=400)
        enquiry=get_object_or_404(WebsiteEnquiry,pk=identifier)
        enquiry.status=data['status'];enquiry.save(update_fields=['status'])
        return JsonResponse({'id':str(enquiry.pk),'status':enquiry.status})
    # Capture the unread IDs before listing. A later arrival is not acknowledged by this response.
    unread_ids=list(unread(request.user).values_list('pk',flat=True))
    page=Paginator(WebsiteEnquiry.objects.order_by('-created_at','-pk'),25).get_page(request.GET.get('page'))
    return JsonResponse({'unread_ids':[str(pk) for pk in unread_ids],
        'results':[dict(id=str(e.pk),reference=e.reference,name=e.name,email=e.email,phone=e.phone,
            client_type=e.client_type,address=e.area,service=e.service,details=e.details,status=e.status,
            status_label=e.get_status_display(),created_at=e.created_at.isoformat()) for e in page],
        'page':page.number,'pages':page.paginator.num_pages,'has_next':page.has_next(),'has_previous':page.has_previous()})


@staff_only(can_schedule)
@require_POST
def mark_read(request):
    try:
        data=payload(request,('ids',));ids=data.get('ids')
        if not isinstance(ids,list) or len(ids)>200 or any(not isinstance(value,str) for value in ids):raise ValueError()
        ids={uuid.UUID(value) for value in ids}
    except (ValueError,TypeError,AttributeError):return JsonResponse({'error':'Send up to 200 valid enquiry IDs.'},status=400)
    existing=WebsiteEnquiry.objects.filter(pk__in=ids).values_list('pk',flat=True)
    WebsiteEnquiryReadReceipt.objects.bulk_create([WebsiteEnquiryReadReceipt(enquiry_id=pk,user=request.user) for pk in existing],ignore_conflicts=True)
    return JsonResponse({'unread':unread(request.user).count()})
