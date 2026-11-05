"""Scoped account lifecycle actions. History is retained; accounts never change agency."""
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.db import transaction
from django.http import HttpResponseForbidden, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from uuid import UUID
from .models import Agency, Audit, Invitation, Membership, Property, Tenancy, User


class Confirmation(forms.Form):
    reason = forms.CharField(max_length=500, widget=forms.Textarea(attrs={'rows': 3}))
    confirm = forms.BooleanField(label='I confirm this change and its effect on access.')


def scope(request, agency_id):
    agency = get_object_or_404(Agency, pk=agency_id)
    if not request.user.is_superuser and not Membership.objects.filter(
            user=request.user, agency=agency, role=Membership.ADMIN).exists():
        return None
    return agency


@login_required
def accounts(request, agency_id):
    agency = scope(request, agency_id)
    if agency is None:
        return HttpResponseForbidden('Agency administrator access required.')
    return render(request, 'portal/accounts.html', {
        'agency': agency,
        'members': Membership.objects.filter(agency=agency).select_related('user'),
        'tenancies': Tenancy.objects.filter(property__agency=agency, active=True).select_related('property'),
        'invitations': Invitation.objects.filter(agency=agency, accepted_at=None, revoked_at=None,
                                                  expires_at__gt=timezone.now()),
        'events': AccountLifecycleEvent.objects.filter(agency=agency).select_related('actor').order_by('-created_at')[:100],
    })


@login_required
def change(request, agency_id, kind, object_id):
    agency = scope(request, agency_id)
    if agency is None:
        return HttpResponseForbidden('Agency administrator access required.')
    if kind not in ('deactivate', 'reactivate', 'move-out', 'cancel-invitation'):
        return HttpResponse(status=404)
    try:
        if kind in ('deactivate', 'reactivate'):
            object_id = int(object_id)
        else:
            object_id = UUID(object_id)
    except (ValueError, TypeError):
        return HttpResponse(status=404)
    form = Confirmation(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            Agency.objects.select_for_update().get(pk=agency.pk)
            if kind in ('deactivate', 'reactivate'):
                membership = get_object_or_404(Membership, agency=agency, user_id=object_id)
                target = User.objects.select_for_update().get(pk=membership.user_id)
                if target.pk == request.user.pk or target.is_staff or target.is_superuser or membership.role == Membership.ADMIN:
                    return HttpResponseForbidden('Protected account. Arrange a separately reviewed administrator change.')
                target.is_active = kind == 'reactivate'
                target.session_version += 1
                target.save(update_fields=['is_active', 'session_version'])
                if kind == 'deactivate':
                    Tenancy.objects.filter(user=target, property__agency=agency, active=True).update(active=False)
                    Property.objects.filter(agency=agency, manager=target).update(manager=None)
                    Invitation.objects.filter(agency=agency, email__iexact=target.email,
                                              accepted_at=None, revoked_at=None).update(revoked_at=timezone.now())
            elif kind == 'move-out':
                tenancy = get_object_or_404(Tenancy.objects.select_for_update(), pk=object_id, property__agency=agency)
                tenancy.active = False
                tenancy.save(update_fields=['active'])
                Invitation.objects.filter(tenancy=tenancy, accepted_at=None, revoked_at=None).update(revoked_at=timezone.now())
            else:
                invitation = get_object_or_404(Invitation.objects.select_for_update(), pk=object_id, agency=agency)
                if invitation.revoked_at:
                    form.add_error(None, 'This invitation was already cancelled or replaced.')
                elif invitation.accepted_at:
                    form.add_error(None, 'This invitation was already accepted. Manage the account instead.')
                else:
                    invitation.revoked_at = timezone.now()
                    invitation.save(update_fields=['revoked_at'])
                    if invitation.tenancy_id:
                        Tenancy.objects.filter(pk=invitation.tenancy_id, user=None).update(active=False)
            if not form.errors:
                Audit.objects.create(agency=agency, actor=request.user, action=kind,
                                     object_id=str(object_id))
                # Reasons are private to account administrators, never job/customer APIs.
                AccountLifecycleEvent.objects.create(agency=agency, actor=request.user,
                    action=kind, object_reference=str(object_id), reason=form.cleaned_data['reason'])
                messages.success(request, 'Access change saved. Existing history has been retained.')
                return redirect('agency_accounts', agency_id=agency.pk)
    return render(request, 'portal/form.html', {'form': form,
        'title': kind.replace('-', ' ').title() + ' · historical records will be retained'})


def accept_existing_tenant(request, invitation, existing):
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    if request.user.pk != existing.pk:
        return HttpResponseForbidden('Sign in with the invited tenant account.')
    form = forms.Form(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            Agency.objects.select_for_update().get(pk=invitation.agency_id)
            user = User.objects.select_for_update().get(pk=existing.pk)
            invitation = Invitation.objects.select_for_update().get(pk=invitation.pk)
            if (not user.is_active or invitation.accepted_at or invitation.revoked_at or
                    invitation.expires_at <= timezone.now() or not Membership.objects.filter(
                        user=user, agency=invitation.agency, role=Membership.TENANT).exists()):
                return HttpResponse('Invitation unavailable.', status=410)
            tenancy = get_object_or_404(Tenancy.objects.select_for_update(), pk=invitation.tenancy_id,
                active=True, property__agency=invitation.agency, email__iexact=user.email)
            if tenancy.user_id not in (None, user.pk):
                return HttpResponse('Invitation unavailable.', status=410)
            tenancy.user = user
            tenancy.save(update_fields=['user'])
            invitation.accepted_at = timezone.now()
            invitation.save(update_fields=['accepted_at'])
            Audit.objects.create(agency=invitation.agency, actor=user,
                                 action='Existing tenant accepted property link', object_id=str(tenancy.pk))
        return redirect('dashboard')
    return render(request, 'portal/accept_existing.html', {'form': form, 'invitation': invitation})


from .models import AccountLifecycleEvent
