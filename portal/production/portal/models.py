import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.functions import Lower
from django.utils import timezone
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


class MaintenanceRequest(models.Model):
    class Status(models.TextChoices):
        AWAITING_REVIEW = 'awaiting_review', 'Awaiting property manager review'
        REVIEWED = 'reviewed', 'Reviewed'
        IN_PROGRESS = 'in_progress', 'In progress'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(Property, on_delete=models.PROTECT, related_name='maintenance_requests')
    reported_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='maintenance_requests')
    title = models.CharField(max_length=180)
    description = models.TextField(max_length=2500)
    category = models.CharField(max_length=80)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.AWAITING_REVIEW)
    version = models.PositiveIntegerField(default=1)
    submission_key = models.UUIDField(null=True, blank=True, unique=True)
    submission_fingerprint = models.CharField(max_length=64, blank=True)
    # Deliberately never included in the public API or portal payload.
    internal_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['property', 'status'], name='maintenance_property_status')]
        constraints = [models.CheckConstraint(condition=models.Q(status__in=[
            'awaiting_review', 'reviewed', 'in_progress', 'completed', 'cancelled'
        ]), name='maintenance_valid_status')]


class MaintenanceStatusEvent(models.Model):
    request = models.ForeignKey(MaintenanceRequest, on_delete=models.PROTECT, related_name='status_events')
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    status = models.CharField(max_length=24, choices=MaintenanceRequest.Status.choices)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['at', 'id']


class MaintenanceAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(MaintenanceRequest, on_delete=models.PROTECT, related_name='attachments')
    uploaded_by = models.ForeignKey(User, on_delete=models.PROTECT)
    storage_key = models.CharField(max_length=200, unique=True)
    filename = models.CharField(max_length=160)
    content_type = models.CharField(max_length=40)
    size = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']


class JobComment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(MaintenanceRequest, on_delete=models.PROTECT, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.PROTECT)
    author_name = models.CharField(max_length=300)
    author_role = models.CharField(max_length=20)
    text = models.TextField(max_length=2500)
    idempotency_key = models.UUIDField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']


class JobQuotation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(MaintenanceRequest, on_delete=models.PROTECT, related_name='quotations')
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='+')
    title = models.CharField(max_length=180)
    scope = models.TextField(max_length=3000)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=12, choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending')
    version = models.PositiveIntegerField(default=1)
    creation_key = models.UUIDField(unique=True)
    decision_key = models.UUIDField(null=True, blank=True, unique=True)
    decided_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    decision_reason = models.TextField(max_length=1000, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name='quotation_positive_amount'),
            models.CheckConstraint(condition=models.Q(status__in=['pending', 'approved', 'rejected']), name='quotation_valid_status'),
        ]


class JobActivity(models.Model):
    class Kind(models.TextChoices):
        SUBMITTED = 'job_submitted', 'Maintenance request submitted'
        STATUS = 'status_changed', 'Status changed'
        COMMENT = 'comment_added', 'Shared comment added'
        QUOTE_CREATED = 'quote_created', 'Quotation issued'
        QUOTE_APPROVED = 'quote_approved', 'Quotation approved'
        QUOTE_REJECTED = 'quote_rejected', 'Quotation rejected'
        CANCELLED = 'job_cancelled', 'Job cancelled'
        COMPLETED = 'job_completed', 'Job completed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(MaintenanceRequest, on_delete=models.PROTECT, related_name='activities')
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    actor_name = models.CharField(max_length=300)
    actor_role = models.CharField(max_length=20)
    kind = models.CharField(max_length=24, choices=Kind.choices)
    dedup_key = models.CharField(max_length=200, unique=True)
    details = models.JSONField(default=dict)
    job_title = models.CharField(max_length=180)
    property_name = models.CharField(max_length=180)
    property_address = models.CharField(max_length=400)
    agency_name = models.CharField(max_length=180)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ['created_at', 'id']


class OperationsNotification(models.Model):
    event = models.OneToOneField(JobActivity, on_delete=models.PROTECT, related_name='operations_notification')
    recipient = models.EmailField()
    state = models.CharField(max_length=12, choices=[('pending', 'Pending'), ('sending', 'Sending'), ('sent', 'Sent'), ('dead', 'Failed')], default='pending')
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    lease_token = models.UUIDField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['state', 'next_attempt_at'], name='operations_delivery_due')]


class OperationsDeliveryAttempt(models.Model):
    notification = models.ForeignKey(OperationsNotification, on_delete=models.PROTECT, related_name='delivery_attempts')
    number = models.PositiveIntegerField()
    outcome = models.CharField(max_length=12, default='sending')
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ['number']
        constraints = [models.UniqueConstraint(fields=['notification', 'number'], name='operations_attempt_number_unique')]
