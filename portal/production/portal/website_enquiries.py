"""Public enquiries are leads, never automatic customer accounts or booked jobs."""
import hashlib
import json
import uuid
from datetime import timedelta
from django import forms
from django.core import signing
from django.db import transaction, IntegrityError
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from .models import WebsiteEnquiry, MailQueue
from .services import limited
from .staff_access import can_schedule

SALT = 'sevlink-website-enquiry'

class EnquiryForm(forms.Form):
    name = forms.CharField(max_length=100)
    phone = forms.CharField(max_length=30)
    email = forms.EmailField(max_length=254)
    clientType = forms.ChoiceField(choices=[(v,v) for v in ['Homeowner / private client','Landlord','Property agency']])
    area = forms.CharField(max_length=400)
    service = forms.CharField(max_length=80)
    details = forms.CharField(max_length=2500)
    consent = forms.BooleanField()
    submission_token = forms.CharField(max_length=300)
    website = forms.CharField(required=False, max_length=200)

    def clean_service(self):
        from .maintenance import CATEGORIES
        value = self.cleaned_data['service']
        if value not in (*CATEGORIES, 'Not sure / something else'):
            raise forms.ValidationError('Choose a service from the list.')
        return value

    def clean(self):
        data = super().clean()
        if data.get('website'):
            raise forms.ValidationError('Unable to submit this enquiry.')
        try:
            data['key'] = uuid.UUID(signing.loads(data.get('submission_token',''), salt=SALT, max_age=86400))
        except (signing.BadSignature, ValueError, TypeError):
            raise forms.ValidationError('Refresh this page and submit again.')
        return data

@never_cache
@require_http_methods(['GET','HEAD','POST'])
def public_landing(request):
    if request.method != 'POST':
        return render(request, 'portal/landing.html', {'submission_token':signing.dumps(str(uuid.uuid4()),salt=SALT)})
    form = EnquiryForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'error':'Please check your details.', 'fields':form.errors},status=400)
    d = form.cleaned_data
    values = {k:d[k] for k in ['name','phone','email','clientType','area','service','details']}
    values['email'] = values['email'].lower()
    fingerprint = hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()
    existing = WebsiteEnquiry.objects.filter(submission_key=d['key']).first()
    if existing:
        if existing.fingerprint != fingerprint:
            return JsonResponse({'error':'This form was already submitted. Refresh to start a new enquiry.'}, status=409)
        return JsonResponse({'reference':existing.reference})
    # REMOTE_ADDR is the proxy on this deployment; also cap overall traffic rather than trusting forwarded IPs.
    if limited('website-enquiry-total', maximum=100) or limited('website-enquiry-email:'+values['email'], maximum=3):
        return JsonResponse({'error':'Too many enquiries. Please try again in 15 minutes or call 081 028 5034.'},status=429)
    try:
        with transaction.atomic():
            enquiry = WebsiteEnquiry.objects.create(submission_key=d['key'],fingerprint=fingerprint,
                name=d['name'],phone=d['phone'],email=values['email'],client_type=d['clientType'],
                area=d['area'],service=d['service'],details=d['details'])
            for recipient, subject in [('maintenance@sevlink.co.za','New website enquiry'),(enquiry.email,'We received your enquiry')]:
                body = email_text(enquiry, recipient)
                MailQueue.objects.create(website_enquiry=enquiry,recipient=recipient,
                    subject=f'{subject} | {enquiry.reference}',body=body,expires_at=timezone.now()+timedelta(days=7))
    except IntegrityError:
        enquiry = WebsiteEnquiry.objects.filter(submission_key=d['key'],fingerprint=fingerprint).first()
        if enquiry is None:
            raise
    return JsonResponse({'reference':enquiry.reference},status=201)


def email_text(enquiry, recipient):
    staff = recipient == 'maintenance@sevlink.co.za'
    intro = 'A new property enquiry has been received.' if staff else f'Thank you, {enquiry.name}. We have received your property enquiry.'
    return (f'{intro}\n\nReference: {enquiry.reference}\n\n'
        f'CONTACT DETAILS\nName: {enquiry.name}\nPhone: {enquiry.phone}\nEmail: {enquiry.email}\nEnquiring as: {enquiry.client_type}\n\n'
        f'PROPERTY & SERVICE\nProperty address: {enquiry.area}\nService: {enquiry.service}\n\nWORK REQUESTED\n{enquiry.details}\n\n'
        + ('Open Website enquiries in your Sevlink dashboard to follow up.' if staff else
        'Our team will contact you to discuss the work and next step. This is an enquiry, not a confirmed booking.\nFor urgent assistance, call 081 028 5034.'))


def email_bodies(enquiry, recipient):
    if enquiry.service=='Agency consultation':
        from .agency_enquiries import email_bodies as agency_email_bodies
        return agency_email_bodies(enquiry,recipient)
    from .email_branding import branded_bodies
    staff = recipient == 'maintenance@sevlink.co.za'
    rows = format_html_join('', '<tr><td style="padding:9px 0;width:36%;color:#597182;vertical-align:top">{}</td><td style="padding:9px 0;font-weight:600">{}</td></tr>',
        [('Name',enquiry.name),('Phone',enquiry.phone),('Email',enquiry.email),('Enquiring as',enquiry.client_type),('Property address',enquiry.area),('Service',enquiry.service)])
    details = format_html_join(format_html('<br>'), '{}', ((line,) for line in enquiry.details.splitlines()))
    content = format_html('<p style="color:#24868a;font-size:12px;letter-spacing:2px">SEVLINK PROPERTY CARE</p>'
        '<h1 style="font-size:26px;color:#102e46">{}</h1><p>{}</p>'
        '<p style="padding:12px 16px;background:#edf7f7;border-radius:8px"><b>Reference: {}</b></p>'
        '<h2 style="font-size:17px">Enquiry details</h2><table role="presentation" width="100%" cellspacing="0">{}</table>'
        '<h2 style="font-size:17px;margin-top:24px">Work requested</h2><div style="padding:18px;background:#f3f7fa;border-radius:10px">{}</div>'
        '<p style="margin-top:24px">{}</p>{}',
        'New property enquiry' if staff else 'Your enquiry is with us',
        'Ready for your team to review and follow up.' if staff else f'Thank you, {enquiry.name}. We have saved your enquiry and our team will contact you.',
        enquiry.reference,rows,details,
        'Follow up from Website enquiries in your Sevlink dashboard.' if staff else 'This is an enquiry, not a confirmed booking. For urgent assistance, call 081 028 5034.',
        format_html('<p><a href="https://portal.sevlink.co.za/enquiries/" style="color:#247b83">Open website enquiries →</a></p>') if staff else '')
    return branded_bodies(email_text(enquiry,recipient),content_html=content)

@login_required
@never_cache
@require_http_methods(['GET','POST'])
def inbox(request):
    if not (request.user.is_active and (request.user.is_superuser or can_schedule(request.user))):
        return HttpResponseForbidden('Sevlink staff access required.')
    if request.method == 'POST':
        status = request.POST.get('status')
        if status not in ('new','contacted','closed'):
            return JsonResponse({'error':'Invalid status.'},status=400)
        try:
            enquiry_id = uuid.UUID(request.POST.get('id',''))
        except ValueError:
            return JsonResponse({'error':'Invalid enquiry.'},status=400)
        WebsiteEnquiry.objects.filter(pk=enquiry_id).update(status=status)
        return redirect('website_enquiries')
    return redirect('/maintenance/?view=websiteEnquiries')
