"""Public subcontractor interest leads; does not create accounts, suppliers or jobs."""
import hashlib
import json
import uuid
from datetime import timedelta
from django import forms
from django.core import signing
from django.db import transaction, IntegrityError
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from .agency_enquiries import AgencyEnquiryForm
from .maintenance import CATEGORIES
from .models import WebsiteEnquiry, MailQueue
from .services import limited

SALT='sevlink-subcontractor-interest'
SERVICE='Subcontractor application'

class PartnerForm(forms.Form):
    business=forms.CharField(label='Business / trading name',max_length=180)
    name=forms.CharField(label='Contact name and surname',max_length=100)
    phone=forms.CharField(label='Contact number',max_length=30,widget=forms.TextInput(attrs={'type':'tel'}))
    email=forms.EmailField(label='Email address',max_length=254)
    trade=forms.ChoiceField(label='Primary trade',choices=[('', 'Select your trade')]+[(c,c) for c in CATEGORIES])
    area=forms.CharField(label='Service areas',max_length=180)
    details=forms.CharField(label='Experience and availability',max_length=2000,widget=forms.Textarea(attrs={'rows':4}))
    consent=forms.BooleanField(label='I agree that Sevlink may contact me about this application.')
    submission_token=forms.CharField(max_length=300,widget=forms.HiddenInput)
    website=forms.CharField(required=False,max_length=200,widget=forms.HiddenInput)
    clean_phone=AgencyEnquiryForm.clean_phone

    def clean(self):
        d=super().clean()
        if d.get('website'):raise forms.ValidationError('Unable to submit this request.')
        try:d['key']=uuid.UUID(signing.loads(d.get('submission_token',''),salt=SALT,max_age=86400))
        except (ValueError,TypeError,signing.BadSignature):raise forms.ValidationError('Refresh this page and submit again.')
        return d

@never_cache
@require_http_methods(['GET','HEAD','POST'])
def apply(request):
    if request.method!='POST':
        receipt=request.GET.get('received')
        if receipt:
            try:
                key=uuid.UUID(signing.loads(receipt,salt=SALT+'-receipt',max_age=86400))
                return render(request,'portal/partner_enquiry.html',{'reference':'WEB-'+key.hex[:12].upper()})
            except (ValueError,TypeError,signing.BadSignature):pass
        return render(request,'portal/partner_enquiry.html',{'form':PartnerForm(initial={'submission_token':signing.dumps(str(uuid.uuid4()),salt=SALT)})})
    form=PartnerForm(request.POST);status=400
    if form.is_valid():
        d=form.cleaned_data;values={k:d[k] for k in ('business','name','phone','email','trade','area','details')};values['email']=values['email'].lower()
        fingerprint=hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()
        existing=WebsiteEnquiry.objects.filter(submission_key=d['key']).first()
        if existing and existing.fingerprint!=fingerprint:form.add_error(None,'This form was already submitted. Refresh to start another request.');status=409
        elif existing:return received(existing)
        elif limited('partner-enquiry-total',maximum=100) or limited('partner-enquiry-email:'+values['email'],maximum=3):form.add_error(None,'Too many requests. Try again in 15 minutes or call 081 028 5034.');status=429
        else:
            try:
                with transaction.atomic():
                    enquiry=WebsiteEnquiry.objects.create(submission_key=d['key'],fingerprint=fingerprint,name=d['name'],phone=d['phone'],email=values['email'],client_type='Subcontractor',area=d['area'],service=SERVICE,details='Business: '+d['business']+'\nTrade: '+d['trade']+'\nService areas: '+d['area']+'\nExperience and availability: '+d['details'])
                    for recipient in ('maintenance@sevlink.co.za',enquiry.email):
                        MailQueue.objects.create(website_enquiry=enquiry,recipient=recipient,subject=('New subcontractor application' if recipient=='maintenance@sevlink.co.za' else 'We received your subcontractor application')+' | '+enquiry.reference,body=email_text(enquiry,recipient),expires_at=timezone.now()+timedelta(days=7))
            except IntegrityError:
                enquiry=WebsiteEnquiry.objects.filter(submission_key=d['key'],fingerprint=fingerprint).first()
                if enquiry is None:raise
            return received(enquiry)
    return render(request,'portal/partner_enquiry.html',{'form':form},status=status)

def received(enquiry):
    return redirect(reverse('partner_apply')+'?received='+signing.dumps(str(enquiry.pk),salt=SALT+'-receipt'))

def email_text(enquiry,recipient):
    staff=recipient=='maintenance@sevlink.co.za'
    return '\n\n'.join(['A new subcontractor application has been received.' if staff else 'Thank you. We received your subcontractor application.',
        'Reference: '+enquiry.reference,'Contact: '+enquiry.name+'\nPhone: '+enquiry.phone+'\nEmail: '+enquiry.email,enquiry.details,
        'Follow up from Website enquiries in the Sevlink dashboard.' if staff else 'Sevlink will contact you to discuss your application. This is not a supplier approval, account activation or allocation of work.'])

def email_bodies(enquiry,recipient):
    from .email_branding import branded_bodies
    return branded_bodies(email_text(enquiry,recipient))
