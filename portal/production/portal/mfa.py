"""Local authenticator enrollment. No external QR service or email is involved."""
from django import forms
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice
from .models import PrivilegedSecurityEvent
from .services import limited


class Enrollment(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput, label='Current password')


class Verification(forms.Form):
    token = forms.CharField(max_length=8, min_length=6, label='Authenticator code',
                           widget=forms.TextInput(attrs={'autocomplete':'one-time-code','inputmode':'numeric'}))


@login_required
@never_cache
@sensitive_post_parameters('password', 'token')
def verify(request):
    if not (request.user.is_active and (request.user.is_staff or request.user.is_superuser)):
        return HttpResponseForbidden('Privileged account required.')
    confirmed = TOTPDevice.objects.filter(user=request.user, confirmed=True).first()
    pending = TOTPDevice.objects.filter(user=request.user, confirmed=False).first()
    form_class = Verification if confirmed or pending else Enrollment
    form = form_class(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        if limited('mfa:'+str(request.user.pk),maximum=10):
            return HttpResponseForbidden('Too many attempts. Try again in 15 minutes.')
        # Serialize enrollment/verification; django-otp also throttles and rejects reused tokens.
        from .models import User
        with transaction.atomic():
            User.objects.select_for_update().get(pk=request.user.pk)
            device = TOTPDevice.objects.select_for_update().filter(user=request.user,confirmed=True).first()
            pending = TOTPDevice.objects.select_for_update().filter(user=request.user,confirmed=False).first()
            if not device and not pending and 'password' in form.cleaned_data:
                if request.user.check_password(form.cleaned_data['password']):
                    TOTPDevice.objects.create(user=request.user,name='Sevlink authenticator',confirmed=False)
                    PrivilegedSecurityEvent.objects.create(user=request.user,action='MFA enrollment started')
                    return redirect('mfa_verify')
                form.add_error(None,'Unable to verify your password.')
            elif device or pending:
                candidate = device or pending
                if 'token' in form.cleaned_data and candidate.verify_token(form.cleaned_data['token']):
                    if not candidate.confirmed:
                        candidate.confirmed=True
                        candidate.save(update_fields=['confirmed'])
                        PrivilegedSecurityEvent.objects.create(user=request.user,action='MFA enrolled')
                    else:
                        PrivilegedSecurityEvent.objects.create(user=request.user,action='MFA session verified')
                    otp_login(request,candidate)
                    return redirect('dashboard')
                form.add_error(None,'Invalid, expired or already-used code. Try a fresh code.')
    import base64
    setup_key = base64.b32encode(pending.bin_key).decode() if pending and not confirmed else ''
    response = render(request,'portal/mfa.html',{'form':form,'pending':pending if not confirmed else None,'setup_key':setup_key})
    response['Referrer-Policy']='same-origin'
    response['Content-Security-Policy']="default-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'self'"
    return response
