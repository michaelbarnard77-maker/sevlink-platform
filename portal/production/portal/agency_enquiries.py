"""Public agency consultation leads. Never creates accounts or invitations."""
import hashlib
import json
import re
import uuid
from datetime import timedelta
from django import forms
from django.core import signing
from django.db import transaction, IntegrityError
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from .models import WebsiteEnquiry, MailQueue
from .services import limited

SALT='sevlink-agency-consultation'
SERVICE='Agency consultation'
INTERESTS=[('learn','I’d like to learn more about Sevlink'),('demo','I’d like a demonstration of the portal'),('onboard','I’m interested in onboarding our agency')]
TIMEFRAMES=[('exploring','Just exploring — no timeframe yet'),('three_months','Within the next 3 months'),('soon','As soon as possible')]

class AgencyEnquiryForm(forms.Form):
    agency=forms.CharField(max_length=180,label='Agency name',widget=forms.TextInput(attrs={'placeholder':'Your agency’s name','autocomplete':'organization'}))
    first=forms.CharField(max_length=49,label='Administrator’s first name',widget=forms.TextInput(attrs={'placeholder':'First name','autocomplete':'given-name'}))
    last=forms.CharField(max_length=49,label='Administrator’s surname',widget=forms.TextInput(attrs={'placeholder':'Surname','autocomplete':'family-name'}))
    phone=forms.CharField(max_length=30,label='Contact number',widget=forms.TextInput(attrs={'type':'tel','placeholder':'e.g. 082 123 4567','autocomplete':'tel'}))
    email=forms.EmailField(label='Email address',widget=forms.EmailInput(attrs={'placeholder':'you@youragency.co.za','autocomplete':'email'}))
    interest=forms.ChoiceField(label='How can we help?',choices=[('','Select an option')]+INTERESTS)
    timeframe=forms.ChoiceField(label='Preferred onboarding timeframe',choices=[('','Select your timeframe')]+TIMEFRAMES)
    consent=forms.BooleanField(label='I agree that Sevlink may contact me about this enquiry and agency onboarding.')
    submission_token=forms.CharField(max_length=300,widget=forms.HiddenInput)
    website=forms.CharField(required=False,max_length=200,widget=forms.HiddenInput)

    def clean_phone(self):
        phone=self.cleaned_data['phone'].strip()
        if not re.fullmatch(r'[+()0-9 .-]{7,30}',phone) or len(re.sub(r'\D','',phone))<7:
            raise forms.ValidationError('Enter a valid contact number.')
        return phone

    def clean(self):
        data=super().clean()
        if data.get('website'):raise forms.ValidationError('Unable to submit this enquiry.')
        try:data['key']=uuid.UUID(signing.loads(data.get('submission_token',''),salt=SALT,max_age=86400))
        except (ValueError,TypeError,signing.BadSignature):raise forms.ValidationError('Refresh this page and submit again.')
        return data

@never_cache
@require_http_methods(['GET','HEAD','POST'])
def public_enquiry(request):
    if request.method!='POST':
        receipt=request.GET.get('received')
        if receipt:
            try:
                key=uuid.UUID(signing.loads(receipt,salt=SALT+'-receipt',max_age=86400))
                return render(request,'portal/agency_enquiry.html',{'reference':'WEB-'+key.hex[:12].upper()})
            except (ValueError,TypeError,signing.BadSignature):pass
        form=AgencyEnquiryForm(initial={'submission_token':signing.dumps(str(uuid.uuid4()),salt=SALT)})
        return render(request,'portal/agency_enquiry.html',{'form':form})
    form=AgencyEnquiryForm(request.POST)
    status=400
    if form.is_valid():
        d=form.cleaned_data
        values={k:d[k] for k in ('agency','first','last','phone','email','interest','timeframe')}
        values['email']=values['email'].lower()
        fingerprint=hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()
        enquiry=WebsiteEnquiry.objects.filter(submission_key=d['key']).first()
        if enquiry and enquiry.fingerprint!=fingerprint:
            form.add_error(None,'This form was already submitted. Refresh to start a new enquiry.');status=409
        elif enquiry:
            return receipt_redirect(enquiry)
        elif limited('agency-enquiry-total',maximum=100) or limited('agency-enquiry-email:'+values['email'],maximum=3):
            form.add_error(None,'Too many requests. Please try again in 15 minutes or call 081 028 5034.');status=429
        else:
            try:
                with transaction.atomic():
                    enquiry=WebsiteEnquiry.objects.create(submission_key=d['key'],fingerprint=fingerprint,name=d['first']+' '+d['last'],phone=d['phone'],email=values['email'],client_type='Property agency',area='Agency onboarding',service=SERVICE,
                        details='Agency: '+d['agency']+'\nInterest: '+dict(INTERESTS)[d['interest']]+'\nPreferred onboarding timeframe: '+dict(TIMEFRAMES)[d['timeframe']])
                    for recipient in ('maintenance@sevlink.co.za',enquiry.email):
                        staff=recipient=='maintenance@sevlink.co.za'
                        MailQueue.objects.create(website_enquiry=enquiry,recipient=recipient,subject=('New agency consultation request' if staff else 'We received your agency request')+' | '+enquiry.reference,body=email_text(enquiry,recipient),expires_at=timezone.now()+timedelta(days=7))
            except IntegrityError:
                enquiry=WebsiteEnquiry.objects.filter(submission_key=d['key'],fingerprint=fingerprint).first()
                if enquiry is None:raise
            return receipt_redirect(enquiry)
    return render(request,'portal/agency_enquiry.html',{'form':form},status=status)

def receipt_redirect(enquiry):
    return redirect(reverse('register')+'?received='+signing.dumps(str(enquiry.pk),salt=SALT+'-receipt'))

def email_text(enquiry,recipient):
    staff=recipient=='maintenance@sevlink.co.za'
    return '\n\n'.join(['A new agency consultation request has been received.' if staff else 'Thank you, '+enquiry.name+'. We received your agency request.',
        'Reference: '+enquiry.reference,'CONTACT DETAILS\nAdministrator: '+enquiry.name+'\nContact number: '+enquiry.phone+'\nEmail: '+enquiry.email,
        enquiry.details,'Contact the administrator to arrange a call or meeting. Open Website enquiries in your Sevlink dashboard to follow up.' if staff else 'Sevlink will contact you to discuss your requirements and arrange a suitable time. This request does not create an agency account or confirm a meeting.\nContact: 081 028 5034'])

def email_bodies(enquiry,recipient):
    from .email_branding import branded_bodies
    staff=recipient=='maintenance@sevlink.co.za'
    rows=format_html_join('','<tr><td style="padding:9px 0;color:#597182;width:36%">{}</td><td style="padding:9px 0;font-weight:600">{}</td></tr>',[('Administrator',enquiry.name),('Contact number',enquiry.phone),('Email',enquiry.email)])
    details=format_html_join(format_html('<br>'),'{}',((line,) for line in enquiry.details.splitlines()))
    content=format_html('<p style="color:#24868a;font-size:12px;letter-spacing:2px">SEVLINK · PROPERTY AGENCIES</p><h1 style="font-size:26px;color:#102e46">{}</h1><p>{}</p><p style="padding:12px 16px;background:#edf7f7;border-radius:8px"><b>Reference: {}</b></p><table role="presentation" width="100%">{}</table><h2 style="font-size:17px">Agency consultation</h2><div style="padding:18px;background:#f3f7fa;border-radius:10px">{}</div><p>{}</p>{}',
        'New agency consultation request' if staff else 'Your agency request is with us',
        'Ready for your team to contact the administrator.' if staff else 'Thank you, '+enquiry.name+'. We’ll contact you to discuss your requirements and arrange a suitable time.',enquiry.reference,rows,details,
        'Follow up from Website enquiries in your dashboard.' if staff else 'This request does not create an agency account or confirm a meeting.',
        format_html('<p><a href="https://portal.sevlink.co.za/enquiries/">Open website enquiries →</a></p>') if staff else '')
    return branded_bodies(email_text(enquiry,recipient),content_html=content)
