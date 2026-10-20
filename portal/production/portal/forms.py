from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, Property, Membership
class RegisterForm(UserCreationForm):
    agency_name = forms.CharField(max_length=180,label='Agency name')
    first_name = forms.CharField(max_length=150,label='Your name')
    email = forms.EmailField()
    phone = forms.CharField(max_length=40)
    area = forms.CharField(max_length=180,label='Service area')
    class Meta:
        model = User
        fields = ['agency_name','first_name','email','phone','area','password1','password2']
    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account already uses this email. Sign in or reset your password.')
        return email
class EmailLoginForm(AuthenticationForm):
    username = forms.EmailField(label='Email')
    def clean_username(self):
        return self.cleaned_data['username'].strip().lower()
class InviteForm(forms.Form):
    name = forms.CharField(max_length=150)
    email = forms.EmailField()
    phone = forms.CharField(max_length=40,required=False)
    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account already uses this email. Contact Sevlink to arrange access; an existing account will not be reassigned.')
        return email
class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = ['name','address','manager','access_responsibility','access_notes']
        widgets = {'access_notes':forms.Textarea(attrs={'rows':3})}
    def __init__(self,*args,member,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['manager'].queryset = User.objects.filter(membership__agency=member.agency,membership__role=Membership.PM,is_active=True)
        self.fields['manager'].empty_label = 'Agency administrator manages'
        if member.role == Membership.PM:
            del self.fields['manager']
