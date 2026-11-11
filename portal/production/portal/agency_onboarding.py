"""Owner-managed agency onboarding with private password setup by invitation."""
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction, IntegrityError
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from .models import Agency, User, Membership, Audit, AccountLifecycleEvent
from .services import queue_invite


class AgencyOnboardingForm(forms.Form):
    agency_name = forms.CharField(max_length=180, label='Agency name')
    phone = forms.CharField(max_length=40, label='Agency contact number')
    area = forms.CharField(max_length=180, label='Area / region')
    admin_name = forms.CharField(max_length=150, label='Agency administrator name')
    admin_email = forms.EmailField(label='Agency administrator email')

    def clean_agency_name(self):
        name = self.cleaned_data['agency_name'].strip()
        if Agency.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError('An agency with this name already exists. Open its existing account instead.')
        return name

    def clean_admin_email(self):
        email = self.cleaned_data['admin_email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account already uses this email. Use a separate administrator email; existing accounts cannot be moved to another agency here.')
        return email


@login_required
@require_http_methods(['GET', 'POST'])
def create(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden('Sevlink Super Admin access required.')
    form = AgencyOnboardingForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                # Serialise owner onboarding requests, including repeated submissions.
                User.objects.select_for_update().get(pk=request.user.pk)
                if Agency.objects.filter(name__iexact=form.cleaned_data['agency_name']).exists() or User.objects.filter(email__iexact=form.cleaned_data['admin_email']).exists():
                    raise IntegrityError('Agency or administrator already exists.')
                agency = Agency.objects.create(name=form.cleaned_data['agency_name'], phone=form.cleaned_data['phone'], area=form.cleaned_data['area'], kind='agency')
                email = form.cleaned_data['admin_email']
                user = User.objects.create_user(username=email, email=email, first_name=form.cleaned_data['admin_name'], is_active=False, is_staff=False, is_superuser=False)
                Membership.objects.create(user=user, agency=agency, role=Membership.ADMIN)
                invitation = queue_invite(agency=agency, email=email, name=user.first_name, role=Membership.ADMIN, actor=request.user)
                Audit.objects.create(agency=agency, actor=request.user, action='Agency created; administrator invited', object_id=str(invitation.pk))
                AccountLifecycleEvent.objects.create(agency=agency, actor=request.user, action='agency_onboarded', object_reference=str(user.pk), reason='Owner created agency and queued first administrator invitation.')
            messages.success(request, 'Agency created. An invitation has been queued for '+email+'. They choose their own password using the link, valid for 48 hours. After signing in, they can invite PMs and add properties.')
            return redirect('agency_accounts', agency_id=agency.pk)
        except IntegrityError:
            form.add_error(None, 'This agency or administrator already exists. No duplicate agency was created.')
    return render(request, 'portal/agency_new.html', {'form': form})
