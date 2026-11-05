"""Privileged session verification and bounded per-user API request budgets."""
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect
from .services import limited


class PrivilegedMFAMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if (settings.PRIVILEGED_MFA_REQUIRED and user.is_authenticated and
                (user.is_superuser or user.is_staff) and not user.is_verified() and
                not request.path.startswith(('/security/mfa/', '/logout/'))):
            if request.path.startswith('/api/'):
                return JsonResponse({'error':'Privileged MFA verification required.'},status=403)
            return redirect('mfa_verify')
        return self.get_response(request)


class PortalThrottleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.PORTAL_API_THROTTLING and request.user.is_authenticated and request.path.startswith('/api/'):
            upload = request.META.get('CONTENT_TYPE','').startswith('multipart/form-data')
            kind = 'upload' if upload else 'write' if request.method not in ('GET','HEAD','OPTIONS') else 'read'
            limit = {'upload':settings.PORTAL_UPLOADS_PER_MINUTE,
                     'write':settings.PORTAL_WRITES_PER_MINUTE,
                     'read':settings.PORTAL_READS_PER_MINUTE}[kind]
            if limited(f'api:{request.user.pk}:{kind}',maximum=limit,minutes=1):
                response = JsonResponse({'error':'Request limit reached. Try again shortly.'},status=429)
                response['Retry-After'] = '60'
                return response
        return self.get_response(request)
