import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.functions import Lower
class User(AbstractUser):
    email = models.EmailField(unique=True)
    class Meta:
        constraints = [models.UniqueConstraint(Lower('email'),name='unique_user_email_casefold')]
class Agency(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=180)
    phone = models.CharField(max_length=40)
    area = models.CharField(max_length=180)
    created_at = models.DateTimeField(auto_now_add=True)
class Membership(models.Model):
    ADMIN, PM, TENANT = 'admin', 'pm', 'tenant'
    user = models.OneToOneField(User,on_delete=models.PROTECT,related_name='membership')
    agency = models.ForeignKey(Agency,on_delete=models.PROTECT)
    role = models.CharField(max_length=12,choices=[(ADMIN,'Agency administrator'),(PM,'Property manager'),(TENANT,'Tenant')])
class Property(models.Model):
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    agency = models.ForeignKey(Agency,on_delete=models.PROTECT)
    name = models.CharField(max_length=180)
    address = models.CharField(max_length=400)
    manager = models.ForeignKey(User,null=True,blank=True,on_delete=models.PROTECT)
    access_responsibility = models.CharField(max_length=10,choices=[('sevlink','Sevlink arranges access'),('agency','Agency arranges access')],default='sevlink')
    access_notes = models.TextField(blank=True,max_length=2000)
class Tenancy(models.Model):
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    property = models.ForeignKey(Property,on_delete=models.PROTECT)
    user = models.ForeignKey(User,null=True,blank=True,on_delete=models.PROTECT)
    name = models.CharField(max_length=180)
    email = models.EmailField()
    phone = models.CharField(max_length=40)
    active = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['property','email'],condition=models.Q(active=True),name='unique_active_tenancy_email')]
class Invitation(models.Model):
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    agency = models.ForeignKey(Agency,on_delete=models.PROTECT)
    email = models.EmailField()
    name = models.CharField(max_length=180)
    role = models.CharField(max_length=12)
    tenancy = models.ForeignKey(Tenancy,null=True,blank=True,on_delete=models.PROTECT)
    token_hash = models.CharField(max_length=64,unique=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True,blank=True)
    revoked_at = models.DateTimeField(null=True,blank=True)
    invited_by = models.ForeignKey(User,on_delete=models.PROTECT)
class MailQueue(models.Model):
    recipient = models.EmailField()
    subject = models.CharField(max_length=200)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True,blank=True)
    attempts = models.PositiveIntegerField(default=0)
class Audit(models.Model):
    agency = models.ForeignKey(Agency,on_delete=models.PROTECT)
    actor = models.ForeignKey(User,on_delete=models.PROTECT)
    action = models.CharField(max_length=200)
    object_id = models.CharField(max_length=80,blank=True)
    at = models.DateTimeField(auto_now_add=True)
class RateBucket(models.Model):
    key = models.CharField(max_length=64,primary_key=True)
    start = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)
