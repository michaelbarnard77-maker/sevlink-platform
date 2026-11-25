"""Read-only dashboard projection; reuse the existing portfolio and sharing boundaries."""
from datetime import timedelta
from decimal import Decimal
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET
from .maintenance import api_access, access, requests_for, properties_for, property_data
from .customer_portal import job_row, public_appointments, appointment_row


@api_access
@require_GET
def overview(request):
    role, _ = access(request.user)
    jobs = requests_for(request.user).prefetch_related(None)
    counts = {r['status']: r['total'] for r in jobs.values('status').annotate(total=Count('pk', distinct=True))}
    closed = ('completed', 'closed', 'cancelled')
    active = jobs.exclude(status__in=closed)
    now = timezone.now()
    upcoming = public_appointments(request.user).filter(cancelled_at=None, ends_at__gte=now).exclude(assignment__request__status__in=closed)
    appointments = [appointment_row(a) for a in upcoming[:12]]
    groups = [dict(label=label, count=sum(counts.get(s, 0) for s in states), colour=colour) for label, states, colour in (
        ('New requests', ('awaiting_review',), '#245b5d'),
        ('In progress', ('reviewed', 'in_progress', 'scheduled', 'on_site', 'attended'), '#8ac4ba'),
        ('Completed', ('completed',), '#ead6b2'),
        ('Closed', ('closed',), '#a6adb3'),
        ('Cancelled', ('cancelled',), '#d8dce0'))]
    data = dict(total=sum(counts.values()), active=active.count(), new=counts.get('awaiting_review', 0),
                completed=counts.get('completed', 0)+counts.get('closed', 0),
                closed_30=jobs.filter(status='closed', closed_at__gte=now-timedelta(days=30)).count(),
                groups=groups, appointments=appointments, appointment_count=upcoming.count(), property_count=properties_for(request.user).count(),
                requests=[dict(job_row(j), category=j.category, reported_at=j.created_at.isoformat()) for j in active.order_by('-created_at')[:5]],
                properties=[property_data(p) for p in properties_for(request.user).order_by('address')[:3]])
    if role == 'superadmin':
        # Customer billing only. Supplier invoices and internal costs never enter this projection.
        from .models import JobInvoice
        month = timezone.localdate().replace(day=1)
        data['invoiced_month'] = str(JobInvoice.objects.filter(request__in=jobs,
            visibility='shared', subcontractor=None, document_status='active', created_at__date__gte=month
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0'))
    return JsonResponse(data)
