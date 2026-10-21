"""Operations-only geography, coverage and private assignment foundation."""
import uuid
from functools import wraps

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .events import record
from .maintenance import api_access, payload
from .models import (City, Province, Suburb, Subcontractor, JobAssignment,
                     Property, MaintenanceRequest, Audit)


def operations_only(view):
    @api_access
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_superuser:
            return JsonResponse({'error': 'Sevlink Operations access required.'}, status=403)
        try:
            return view(request, *args, **kwargs)
        except (ValueError, ValidationError):
            return JsonResponse({'error': 'Invalid location, coverage or assignment fields.'}, status=400)
        except IntegrityError:
            return JsonResponse({'error': 'This record already exists or changed. Refresh and retry.'}, status=409)
    return wrapped


def location_values(data):
    values = {}
    for key, model in [('province', Province), ('city', City), ('suburb', Suburb)]:
        value = data.get(key)
        if value not in (None, ''):
            if isinstance(value, bool) or not str(value).isdigit():
                raise ValueError
            values[key] = get_object_or_404(model, pk=int(value))
    if 'suburb' in values:
        city = values['suburb'].city
        if 'city' in values and values['city'].pk != city.pk:
            raise ValueError
        values['city'] = city
    if 'city' in values:
        province = values['city'].province
        if 'province' in values and values['province'].pk != province.pk:
            raise ValueError
        values['province'] = province
    return values


def filter_properties(qs, loc):
    for key in ('suburb', 'city', 'province'):
        if key in loc:
            return qs.filter(**{('city__province' if key == 'province' else key): loc[key]})
    return qs


def coverage(qs, loc):
    # Province-wide coverage includes every city/suburb; city coverage includes
    # all its suburbs. Suburb-only coverage never implies the rest of the city.
    if not loc:
        return qs
    query = Q(provinces=loc['province'])
    if 'city' in loc:
        query |= Q(cities=loc['city'])
        query |= Q(suburbs=loc['suburb']) if 'suburb' in loc else Q(suburbs__city=loc['city'])
    else:
        query |= Q(cities__province=loc['province']) | Q(suburbs__city__province=loc['province'])
    return qs.filter(query).distinct()


def eligible(prop):
    if not prop.city_id:
        return Subcontractor.objects.none()
    loc = {'province': prop.city.province, 'city': prop.city}
    if prop.suburb_id:
        loc['suburb'] = prop.suburb
    # Unknown suburb must not match a suburb-only contractor.
    qs = Subcontractor.objects.filter(active=True, archived=False)
    query = Q(provinces=loc['province']) | Q(cities=loc['city'])
    if 'suburb' in loc:
        query |= Q(suburbs=loc['suburb'])
    return qs.filter(query).distinct()


def contractor_data(item):
    return {'id': str(item.pk), 'name': item.name, 'active': item.active, 'archived': item.archived, 'version': item.version,
            'provinces': list(item.provinces.values_list('pk', flat=True)),
            'cities': list(item.cities.values_list('pk', flat=True)),
            'suburbs': list(item.suburbs.values_list('pk', flat=True))}


def property_data(prop):
    return {'id': str(prop.pk), 'name': prop.name, 'address': prop.address,
            'agency': prop.agency.name, 'city': prop.city_id, 'suburb': prop.suburb_id,
            'province': prop.city.province_id if prop.city_id else None}


def page_data(qs, page, serializer):
    return {'count': qs.count(), 'results': [serializer(item) for item in qs[(page-1)*50:page*50]]}


@operations_only
@require_http_methods(['GET', 'POST'])
def dashboard(request):
    if request.method == 'POST':
        data = payload(request, ('kind', 'name', 'province', 'city'))
        name = data.get('name')
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
            raise ValueError
        loc = location_values(data)
        if data.get('kind') == 'city' and 'province' in loc and set(data) == {'kind', 'name', 'province'}:
            obj = City(province=loc['province'], name=name.strip())
        elif data.get('kind') == 'suburb' and 'city' in loc and set(data) == {'kind', 'name', 'city'}:
            obj = Suburb(city=loc['city'], name=name.strip())
        else:
            raise ValueError
        with transaction.atomic():
            obj.full_clean(); obj.save()
        return JsonResponse({'id': obj.pk}, status=201)
    loc = location_values(request.GET)
    page = int(request.GET.get('page', 1))
    if not 1 <= page <= 1000000:
        raise ValueError
    props = filter_properties(Property.objects.select_related('agency', 'city__province'), loc)
    jobs = MaintenanceRequest.objects.filter(property__in=props).select_related('property__agency', 'property__city__province')
    contractors = coverage(Subcontractor.objects.all(), loc)
    search = request.GET.get('search', '').strip()
    if len(search) > 180: raise ValueError
    if search:
        contractors = contractors.filter(Q(name__icontains=search) | Q(contact_person__icontains=search) | Q(email__icontains=search) | Q(specialisations__icontains=search))
    if request.GET.get('trade'):
        contractors = contractors.filter(trades__name=request.GET['trade'])
    if request.GET.get('status'):
        status = request.GET['status']
        if status not in ('active','inactive','archived'): raise ValueError
        contractors = contractors.filter(archived=True) if status == 'archived' else contractors.filter(archived=False, active=status == 'active')
    from .suppliers import compliance_alerts
    from .models import AssignmentReview, TradeCategory

    return JsonResponse({
        'provinces': list(Province.objects.values('id', 'code', 'name')),
        'cities': list(City.objects.values('id', 'province_id', 'name')),
        'suburbs': list(Suburb.objects.values('id', 'city_id', 'name')),
        'properties': page_data(props.order_by('name', 'pk'), page, property_data),
        'subcontractors': page_data(contractors, page, contractor_data),
        'jobs': page_data(jobs, page, lambda j: {'id': str(j.pk), 'title': j.title,
            'status': j.status, 'property': property_data(j.property)}),
        'page': page,
        'trade_options': list(TradeCategory.objects.values_list('name',flat=True)),
        'compliance_alerts': compliance_alerts(),
        'assignment_reviews': [{'id': r.pk, 'assignment':r.assignment_id, 'reason':r.reason,
            'subcontractor':str(r.assignment.subcontractor_id), 'name':r.assignment.subcontractor.name,
            'job':str(r.assignment.request_id)} for r in AssignmentReview.objects.filter(resolution__isnull=True).select_related('assignment__subcontractor')[:100]],
    })


@operations_only
@require_POST
def contractor(request):
    data = payload(request, ('id', 'name', 'active', 'provinces', 'cities', 'suburbs'))
    if set(data) - {'id'} != {'name', 'active', 'provinces', 'cities', 'suburbs'}:
        raise ValueError
    if not isinstance(data['name'], str) or not data['name'].strip() or len(data['name']) > 180 or type(data['active']) is not bool:
        raise ValueError
    areas = {}
    for key, model in [('provinces', Province), ('cities', City), ('suburbs', Suburb)]:
        ids = data[key]
        if not isinstance(ids, list) or len(ids) > 1000 or any(type(i) is not int for i in ids):
            raise ValueError
        areas[key] = list(model.objects.filter(pk__in=ids))
        if len(areas[key]) != len(set(ids)):
            raise ValueError
    if not any(areas.values()):
        raise ValueError
    with transaction.atomic():
        if data.get('id'):
            item = get_object_or_404(Subcontractor.objects.select_for_update(), pk=uuid.UUID(str(data['id'])))
        else:
            item = Subcontractor(created_by=request.user)
        old = (item.active, *(set(getattr(item,k).values_list('pk',flat=True)) for k in areas)) if not item._state.adding else None
        if item.archived and data['active']: raise ValueError
        item.name = data['name'].strip(); item.active = data['active']
        if old: item.version += 1
        item.full_clean(); item.save()
        for key, values in areas.items():
            getattr(item, key).set(values)
        from .suppliers import flag_assignments, audit
        new = (item.active, *(set(getattr(item,k).values_list('pk',flat=True)) for k in areas))
        if old is not None and old != new:
            flag_assignments(request.user, 'Service coverage or active status changed', subcontractor=item)
        audit(item, request.user, 'Coverage saved')
        result = contractor_data(item)
    return JsonResponse(result)


@operations_only
@require_POST
def property_location(request, property_id):
    data = payload(request, ('city', 'suburb'))
    if not data.get('city'):
        raise ValueError
    loc = location_values(data)
    with transaction.atomic():
        prop = get_object_or_404(Property.objects.select_for_update(), pk=property_id)
        old_location = (prop.city_id, prop.suburb_id)
        prop.city = loc['city']; prop.suburb = loc.get('suburb'); prop.save()
        if old_location != (prop.city_id, prop.suburb_id):
            from .suppliers import flag_assignments
            flag_assignments(request.user, 'Property location changed', request__property=prop)
        Audit.objects.create(agency=prop.agency, actor=request.user, action='Property location mapped', object_id=str(prop.pk))
    return JsonResponse(property_data(prop))


@operations_only
@require_http_methods(['GET', 'POST'])
def assignments(request, job_id):
    job = get_object_or_404(MaintenanceRequest.objects.select_related('property__city__province'), pk=job_id)
    if request.method == 'GET':
        return JsonResponse({'version': job.version, 'location_required': not bool(job.property.city_id),
            'subcontractors': [dict(contractor_data(c), teams=[{'id':str(t.pk),'name':t.name} for t in c.teams.filter(active=True)], team_required=c.teams.exists()) for c in eligible(job.property)],
            'history': [{'id': a.pk, 'subcontractor': str(a.subcontractor_id),
                'name': a.subcontractor.name, 'at': a.created_at.isoformat(),
                'actor': a.actor_id, 'city': a.city_id, 'suburb': a.suburb_id,
                'team':str(a.team_id) if a.team_id else None, 'team_name':a.team.name if a.team_id else 'Legacy / team unallocated',
                'reviews':[{'id':r.pk,'reason':r.reason} for r in a.reviews.filter(resolution__isnull=True)]}
                for a in job.assignments.select_related('subcontractor','team')]})
    data = payload(request, ('subcontractor', 'version', 'submission_key', 'team'))
    if set(data) - {'team'} != {'subcontractor', 'version', 'submission_key'} or type(data['version']) is not int:
        raise ValueError
    key = uuid.UUID(str(data['submission_key'])); contractor_id = uuid.UUID(str(data['subcontractor']))
    with transaction.atomic():
        # Lock only the property row. Its nullable location joins cannot be
        # included in PostgreSQL's default FOR UPDATE lock targets.
        prop = Property.objects.select_for_update().get(pk=job.property_id)
        job = MaintenanceRequest.objects.select_for_update().get(pk=job_id)
        item = get_object_or_404(Subcontractor.objects.select_for_update(), pk=contractor_id)
        from .models import SubcontractorTeam
        team_id = uuid.UUID(str(data['team'])) if data.get('team') else None
        team = get_object_or_404(SubcontractorTeam.objects.select_for_update(), pk=team_id, subcontractor=item) if team_id else None
        prior = JobAssignment.objects.filter(submission_key=key).first()
        if prior:
            if prior.request_id != job.pk or prior.subcontractor_id != item.pk or prior.actor_id != request.user.pk or prior.team_id != team_id:
                return JsonResponse({'error': 'Submission key conflicts with an earlier assignment.'}, status=409)
            return JsonResponse({'id': prior.pk})
        if job.version != data['version'] or job.status in ('completed', 'cancelled'):
            return JsonResponse({'error': 'Job changed or is closed. Refresh before assigning.'}, status=409)
        if not eligible(prop).filter(pk=item.pk).exists():
            return JsonResponse({'error': 'Subcontractor does not cover the mapped property location or is inactive.'}, status=400)
        if (item.teams.exists() and not team) or (team and not team.active):
            return JsonResponse({'error':'Select an active team belonging to this subcontractor.'},status=400)
        current = job.assignments.first()
        if current and current.appointments.filter(cancelled_at__isnull=True, ends_at__gte=timezone.now()).exists():
            return JsonResponse({'error':'Cancel/reschedule the existing appointment before reassigning.'},status=409)
        if current and current.subcontractor_id == item.pk and current.team_id == team_id:
            return JsonResponse({'error': 'Subcontractor is already assigned.'}, status=409)
        assignment = JobAssignment.objects.create(request=job, subcontractor=item, actor=request.user,
            submission_key=key, city=prop.city, suburb=prop.suburb, team=team)
        job.version += 1; job.save(update_fields=['version', 'updated_at'])
        record(job, request.user, 'job_assigned', 'assignment:' + str(key),
               {'assignment_id': str(assignment.pk), 'subcontractor_id': str(item.pk)}, private=True)
    return JsonResponse({'id': assignment.pk}, status=201)
