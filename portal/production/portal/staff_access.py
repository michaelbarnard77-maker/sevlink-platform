"""Explicit private staff capabilities; agency memberships never grant these roles."""
from functools import wraps
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from .models import Membership


def capability(user, permission):
    return user.is_authenticated and user.is_active and (user.is_superuser or (
        user.is_staff and not Membership.objects.filter(user=user).exists() and user.has_perm('portal.'+permission)))


def can_schedule(user): return capability(user,'operate_schedule')


def can_pay(user): return capability(user,'manage_supplier_payments')


def staff_only(check):
    def decorate(view):
        @wraps(view)
        @never_cache
        def wrapped(request,*args,**kwargs):
            if not request.user.is_authenticated: return JsonResponse({'error':'Authentication required.'},status=401)
            if not check(request.user): return JsonResponse({'error':'Authorised Sevlink staff access required.'},status=403)
            return view(request,*args,**kwargs)
        return wrapped
    return decorate
