"""Owner-managed agency onboarding with private password setup by invitation."""
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction, IntegrityError
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from .models import Agency, User, Membership, Audit, AccountLifecycleEvent
from .services import queue_invite, limited
from .forms import InviteForm


class AgencyOnboardingForm(forms.Form):
    agency_name = forms.CharField(max_length=180, label='Agency name')
    phone = forms.CharField(max_length=40, label='Contact number')
    area = forms.CharField(max_length=180, label='Area / region')
    first_role = forms.ChoiceField(label='Who are you onboarding?', required=False, initial=Membership.ADMIN, choices=[(Membership.ADMIN,'Agency administrator — manages the agency and team'),(Membership.PM,'Property manager / agent — manages their own properties')])
    admin_name = forms.CharField(max_length=150, label='Contact’s full name')
    admin_email = forms.EmailField(label='Contact’s email address')

    def clean_first_role(self):
        return self.cleaned_data.get('first_role') or Membership.ADMIN

    def clean_agency_name(self):
        name = self.cleaned_data['agency_name'].strip()
        if Agency.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError('An agency with this name already exists. Open its existing account instead.')
        return name

    def clean_admin_email(self):
        email = self.cleaned_data['admin_email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account already uses this email. Use a separate contact email; existing accounts cannot be moved to another agency here.')
        return email


@login_required
@require_http_methods(['GET', 'POST'])
def create(request):
    if not request.user.is_active or not request.user.is_superuser:
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
                role = form.cleaned_data['first_role']
                user = None
                if role == Membership.ADMIN:
                    user = User.objects.create_user(username=email, email=email, first_name=form.cleaned_data['admin_name'], is_active=False, is_staff=False, is_superuser=False)
                    Membership.objects.create(user=user, agency=agency, role=Membership.ADMIN)
                # A first PM accepts the standard password-setting invitation. No administrator account is required.
                invitation = queue_invite(agency=agency, email=email, name=form.cleaned_data['admin_name'], role=role, actor=request.user)
                Audit.objects.create(agency=agency, actor=request.user, action='Agency created; '+('administrator' if role==Membership.ADMIN else 'PM')+' invited', object_id=str(invitation.pk))
                AccountLifecycleEvent.objects.create(agency=agency, actor=request.user, action='agency_onboarded', object_reference=str(user.pk if user else invitation.pk), reason='Owner created agency and queued first '+role+' invitation.')
            messages.success(request, 'Agency created. An invitation has been queued for '+email+'. They choose their own password using the link, valid for 48 hours. '+('They can manage their own properties and link tenants. No agency administrator account was created.' if role==Membership.PM else 'They can invite PMs, add properties and link tenants.'))
            return redirect('agency_accounts', agency_id=agency.pk)
        except IntegrityError:
            form.add_error(None, 'This agency or contact already exists. No duplicate agency was created.')
    return render(request, 'portal/agency_new.html', {'form': form})


@login_required
@require_http_methods(['GET','POST'])
def invite_property_manager(request,agency_id):
    if not request.user.is_active or not request.user.is_superuser:
        return HttpResponseForbidden('Sevlink Super Admin access required.')
    agency=get_object_or_404(Agency,pk=agency_id,kind='agency')
    form=InviteForm(request.POST if request.method=='POST' else None,agency=agency)
    if request.method=='POST' and form.is_valid():
        if limited('owner-pm-invite:'+str(request.user.pk),maximum=30,minutes=60):
            return HttpResponseForbidden('Invitation limit reached. Try again later.')
        with transaction.atomic():
            Agency.objects.select_for_update().get(pk=agency.pk)
            invitation=queue_invite(agency=agency,email=form.cleaned_data['email'],name=form.cleaned_data['name'],role=Membership.PM,actor=request.user)
            Audit.objects.create(agency=agency,actor=request.user,action='PM invited by Sevlink',object_id=str(invitation.pk))
            AccountLifecycleEvent.objects.create(agency=agency,actor=request.user,action='pm_invited',object_reference=str(invitation.pk),reason='Sevlink directly invited a property manager into this agency.')
        messages.success(request,'Property manager invitation queued. They set their own password and can add their own properties after signing in.')
        return redirect('agency_accounts',agency_id=agency.pk)
    return render(request,'portal/owner_invite_pm.html',{'form':form,'agency':agency})


class DirectPMForm(InviteForm):
    agency = forms.ModelChoiceField(queryset=Agency.objects.none(),required=False,label='Agency (optional)',empty_label='Own PM portfolio — no agency administrator')
    agency_name = forms.CharField(max_length=180,required=False,label='New agency name (optional)')
    area = forms.CharField(max_length=180,required=False,label='Area / region (optional)')

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['agency'].queryset=Agency.objects.filter(kind='agency').order_by('name')
        self.fields['agency'].help_text='Choose an existing agency, or leave this as Own PM portfolio to onboard the PM directly.'
        self.fields['agency_name'].help_text='Only fill this in when creating a new agency record for the PM.'

    def clean(self):
        data=super().clean()
        if data.get('agency') and data.get('agency_name'):
            raise forms.ValidationError('Choose an existing agency or enter a new agency name, not both.')
        name=data.get('agency_name') or 'PM portfolio — '+data.get('name','')
        if not data.get('agency') and Agency.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError('This agency or PM portfolio already exists. Select it from the Agency list.')
        data['portfolio_name']=name
        return data


@login_required
@require_http_methods(['GET','POST'])
def add_pm(request):
    if not request.user.is_active or not request.user.is_superuser:
        return HttpResponseForbidden('Sevlink Super Admin access required.')
    form=DirectPMForm(request.POST if request.method=='POST' else None)
    if request.method=='POST' and form.is_valid():
        try:
            with transaction.atomic():
                User.objects.select_for_update().get(pk=request.user.pk)
                data=form.cleaned_data
                if User.objects.filter(email__iexact=data['email']).exists():raise IntegrityError('Account exists.')
                agency=data.get('agency')
                if agency:
                    agency=Agency.objects.select_for_update().get(pk=agency.pk,kind='agency')
                else:
                    if Agency.objects.filter(name__iexact=data['portfolio_name']).exists():raise IntegrityError('Portfolio exists.')
                    agency=Agency.objects.create(kind='agency',name=data['portfolio_name'],phone=data.get('phone',''),area=data.get('area',''))
                invitation=queue_invite(agency=agency,email=data['email'],name=data['name'],role=Membership.PM,actor=request.user)
                Audit.objects.create(agency=agency,actor=request.user,action='PM invited directly by Sevlink',object_id=str(invitation.pk))
                AccountLifecycleEvent.objects.create(agency=agency,actor=request.user,action='pm_invited',object_reference=str(invitation.pk),reason='Owner added a PM directly; no administrator account created.')
            messages.success(request,'PM invitation queued. They set their own password and can add their own properties. No agency administrator account was created.')
            return redirect('agency_accounts',agency_id=agency.pk)
        except IntegrityError:
            form.add_error(None,'This account or portfolio already exists. Choose the existing portfolio or use the existing account.')
    return render(request,'portal/direct_pm.html',{'form':form})
