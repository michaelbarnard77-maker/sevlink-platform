from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.views import LoginView, PasswordResetView
from django.db import transaction, IntegrityError
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.debug import sensitive_post_parameters
from .models import User, Agency, Membership, Property, Tenancy, Invitation, Audit
from .forms import RegisterForm, InviteForm, PropertyForm, EmailLoginForm
from .services import digest, limited, queue_invite

class PortalLogin(LoginView):
    authentication_form = EmailLoginForm
    template_name = 'registration/login.html'
    def post(self,request,*args,**kwargs):
        if limited('login:'+request.POST.get('username','').strip().lower()) or limited('login-ip:'+request.META.get('REMOTE_ADDR',''),maximum=60):
            return HttpResponse('Too many attempts. Try again in 15 minutes.',status=429)
        return super().post(request,*args,**kwargs)
class PortalPasswordReset(PasswordResetView):
    email_template_name = 'registration/password_reset_email.txt'
    subject_template_name = 'registration/password_reset_subject.txt'
    def post(self,request,*args,**kwargs):
        if limited('reset:'+request.POST.get('email','').lower(),maximum=3) or limited('reset-ip:'+request.META.get('REMOTE_ADDR',''),maximum=30):
            return HttpResponse('Please try again in 15 minutes.',status=429)
        return super().post(request,*args,**kwargs)
    def form_valid(self,form):
        from urllib.parse import urlsplit
        form.save(use_https=settings.SITE_URL.startswith('https:'),domain_override=urlsplit(settings.SITE_URL).netloc,from_email=settings.DEFAULT_FROM_EMAIL,email_template_name=self.email_template_name,subject_template_name=self.subject_template_name,request=self.request)
        return redirect('password_reset_done')
def member(request):
    return Membership.objects.select_related('agency').filter(user=request.user).first()
def properties_for(m):
    if m.role == Membership.ADMIN:
        return Property.objects.filter(agency=m.agency)
    if m.role == Membership.PM:
        return Property.objects.filter(agency=m.agency,manager=m.user)
    if m.role == Membership.TENANT:
        return Property.objects.filter(agency=m.agency,tenancy__user=m.user,tenancy__active=True).distinct()
    return Property.objects.none()
def form_page(request,form,title):
    return render(request,'portal/form.html',{'form':form,'title':title})
@sensitive_post_parameters('password1','password2')
def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if not settings.AGENCY_REGISTRATION_ENABLED:
        return HttpResponse('New agency registration is by prior arrangement. Contact Sevlink.', status=403)
    form = RegisterForm(request.POST if request.method=='POST' else None)
    if request.method=='POST':
        if limited('register:'+request.META.get('REMOTE_ADDR',''),maximum=5,minutes=60):
            return HttpResponse('Please try again in an hour.',status=429)
        if form.is_valid():
            if (settings.AGENCY_REGISTRATION_ALLOWED_EMAILS and
                    form.cleaned_data['email'].casefold() not in settings.AGENCY_REGISTRATION_ALLOWED_EMAILS):
                form.add_error(None, 'Registration is by prior arrangement. Contact Sevlink.')
                return form_page(request, form, 'Create your agency account')
            try:
                with transaction.atomic():
                    user = form.save(commit=False)
                    user.username = form.cleaned_data['email']
                    user.is_active = False
                    user.save()
                    agency = Agency.objects.create(name=form.cleaned_data['agency_name'],phone=form.cleaned_data['phone'],area=form.cleaned_data['area'])
                    Membership.objects.create(user=user,agency=agency,role=Membership.ADMIN)
                    queue_invite(agency=agency,email=user.email,name=user.first_name,role=Membership.ADMIN,actor=user)
                    Audit.objects.create(agency=agency,actor=user,action='Agency registered; verification requested')
                return render(request,'portal/sent.html',{'title':'Verify your email','text':'Your workspace has been created. Open your email verification link before signing in.'})
            except IntegrityError:
                form.add_error(None,'This email is already registered. Sign in or reset your password.')
    return form_page(request,form,'Create your agency account')
@login_required
def dashboard(request):
    m = member(request)
    if not m:
        from .staff_access import can_schedule, can_pay
        if not request.user.is_superuser and (can_schedule(request.user) or can_pay(request.user)):
            return redirect('maintenance_workspace')
        if request.user.is_superuser:
            return render(request,'portal/staff.html',{'agencies':Agency.objects.all(),'property_count':Property.objects.count(),'tenant_count':Tenancy.objects.filter(active=True).count()})
        return HttpResponseForbidden('No workspace access. Contact Sevlink.')
    if m.role not in (Membership.ADMIN, Membership.PM, Membership.TENANT):
        return HttpResponseForbidden('No workspace access. Contact Sevlink.')
    props = properties_for(m).select_related('manager')
    tenants = Tenancy.objects.filter(property__in=props,active=True)
    if m.role==Membership.TENANT:
        tenants = tenants.filter(user=request.user)
    return render(request,'portal/dashboard.html',{'member':m,'properties':props,'tenancies':tenants,'team':Membership.objects.filter(agency=m.agency,role=Membership.PM).select_related('user') if m.role==Membership.ADMIN else [],'invitations':Invitation.objects.filter(agency=m.agency,accepted_at=None,revoked_at=None,expires_at__gt=timezone.now()) if m.role==Membership.ADMIN else []})
@login_required
def invite_pm(request):
    m = member(request)
    if not m or m.role!=Membership.ADMIN:
        return HttpResponseForbidden('Only your agency administrator can invite PMs.')
    return invite_person(request,m)
@login_required
def invite_tenant(request,pid):
    m = member(request)
    if not m or m.role not in [Membership.ADMIN,Membership.PM]:
        return HttpResponseForbidden('Only the agency can link tenants.')
    return invite_person(request,m,get_object_or_404(properties_for(m),pk=pid))
def invite_person(request,m,p=None):
    form = InviteForm(request.POST if request.method=='POST' else None, agency=m.agency, tenant=p is not None)
    if request.method=='POST' and form.is_valid():
        if limited('invite:'+str(request.user.pk),maximum=30,minutes=60):
            return HttpResponse('Invitation limit reached. Try again later.',status=429)
        with transaction.atomic():
            agency = Agency.objects.select_for_update().get(pk=m.agency_id)
            tenancy = None
            if p:
                tenancy,_ = Tenancy.objects.update_or_create(property=p,email=form.cleaned_data['email'],active=True,defaults={'name':form.cleaned_data['name'],'phone':form.cleaned_data['phone']})
            invitation = queue_invite(agency=agency,email=form.cleaned_data['email'],name=form.cleaned_data['name'],role=Membership.TENANT if p else Membership.PM,actor=request.user,tenancy=tenancy)
            Audit.objects.create(agency=agency,actor=request.user,action='Tenant invited' if p else 'PM invited',object_id=str(invitation.pk))
        messages.success(request,'Invitation queued for email delivery. Previous unused links for this email are replaced.')
        return redirect('dashboard')
    return form_page(request,form,'Link tenant · '+p.address if p else 'Invite a property manager')
@login_required
def property_edit(request,pid=None):
    m = member(request)
    if not m or m.role not in [Membership.ADMIN,Membership.PM]:
        return HttpResponseForbidden('Only the agency can manage properties.')
    prop = get_object_or_404(properties_for(m),pk=pid) if pid else Property(agency=m.agency)
    form = PropertyForm(request.POST if request.method=='POST' else None,instance=prop,member=m)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            saved = form.save(commit=False)
            saved.agency = m.agency
            if m.role==Membership.PM:
                saved.manager = request.user
            saved.save()
            Audit.objects.create(agency=m.agency,actor=request.user,action='Property saved',object_id=str(saved.pk))
        return redirect('dashboard')
    return form_page(request,form,'Edit property' if pid else 'Add property')
@sensitive_post_parameters('new_password1','new_password2')
def accept_invitation(request,token):
    invitation = Invitation.objects.select_related('agency','tenancy').filter(token_hash=digest(token),accepted_at=None,revoked_at=None,expires_at__gt=timezone.now()).first()
    if not invitation:
        return render(request,'portal/sent.html',{'title':'Invitation unavailable','text':'This link expired, was replaced or has already been used. Ask your agency for a new invitation.'},status=410)
    existing = User.objects.filter(email__iexact=invitation.email).first()
    if existing and invitation.role == Membership.TENANT:
        from .lifecycle import accept_existing_tenant
        return accept_existing_tenant(request, invitation, existing)
    if request.user.is_authenticated:
        return render(request,'portal/sent.html',{'title':'Sign out first','text':'Sign out before accepting an invitation.'},status=409)
    activation = invitation.role==Membership.ADMIN
    draft = User(username=invitation.email,email=invitation.email,first_name=invitation.name)
    form = forms.Form(request.POST if request.method=='POST' else None) if activation else SetPasswordForm(draft,request.POST if request.method=='POST' else None)
    if request.method=='POST' and form.is_valid():
        try:
            with transaction.atomic():
                Agency.objects.select_for_update().get(pk=invitation.agency_id)
                invitation = Invitation.objects.select_for_update().get(pk=invitation.pk)
                if invitation.accepted_at or invitation.revoked_at or invitation.expires_at<=timezone.now():
                    return HttpResponse('This invitation is no longer available.',status=410)
                if activation:
                    user = User.objects.get(email=invitation.email,is_active=False)
                    user.is_active = True
                    user.save(update_fields=['is_active'])
                else:
                    user = form.save()
                    Membership.objects.create(user=user,agency=invitation.agency,role=invitation.role)
                    if invitation.role==Membership.TENANT:
                        tenancy = Tenancy.objects.select_for_update().get(pk=invitation.tenancy_id,active=True,property__agency=invitation.agency,email=invitation.email)
                        tenancy.user = user
                        tenancy.save(update_fields=['user'])
                invitation.accepted_at = timezone.now()
                invitation.save(update_fields=['accepted_at'])
                Audit.objects.create(agency=invitation.agency,actor=user,action='Agency verified' if activation else 'Invitation accepted',object_id=str(invitation.pk))
            login(request,user,backend='django.contrib.auth.backends.ModelBackend')
            return redirect('dashboard')
        except (IntegrityError,User.DoesNotExist,Tenancy.DoesNotExist):
            form.add_error(None,'Invitation unavailable. Contact your agency for assistance.')
    return render(request,'portal/accept.html',{'form':form,'invitation':invitation,'activation':activation})
def resend_verification(request):
    class EmailForm(forms.Form):
        email = forms.EmailField()
    form = EmailForm(request.POST if request.method=='POST' else None)
    if request.method=='POST' and form.is_valid():
        email = form.cleaned_data['email'].strip().lower()
        if limited('verify:'+email,maximum=3) or limited('verify-ip:'+request.META.get('REMOTE_ADDR',''),maximum=20):
            return HttpResponse('Please try again in 15 minutes.',status=429)
        with transaction.atomic():
            m = Membership.objects.select_related('agency','user').filter(user__email=email,user__is_active=False,role=Membership.ADMIN).first()
            if m:
                Agency.objects.select_for_update().get(pk=m.agency_id)
                queue_invite(agency=m.agency,email=email,name=m.user.first_name,role=Membership.ADMIN,actor=m.user)
        return render(request,'portal/sent.html',{'title':'Check your email','text':'If an agency account is awaiting verification, a replacement link has been queued.'})
    return form_page(request,form,'Resend agency verification')
