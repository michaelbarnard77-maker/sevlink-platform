import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.functions import Lower
from django.utils import timezone
class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        from django.core.exceptions import ValidationError
        raise ValidationError('Audit and conversation records are append-only.')

    def delete(self):
        from django.core.exceptions import ValidationError
        raise ValidationError('Audit and conversation records cannot be deleted.')


class AppendOnlyModel(models.Model):
    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        if not self._state.adding:
            raise ValidationError('Audit and conversation records are append-only.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        raise ValidationError('Audit and conversation records cannot be deleted.')


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
    tenant_comments_allowed = models.BooleanField(default=True)
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
    # Commercial documents are never returned by the general job attachment API.
    purpose = models.CharField(max_length=12, default='general', choices=[('general', 'Job attachment'), ('quotation', 'Quotation PDF'), ('invoice', 'Invoice PDF')])
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(MaintenanceRequest, on_delete=models.PROTECT, related_name='attachments')
    comment = models.ForeignKey('JobComment', null=True, blank=True, on_delete=models.PROTECT, related_name='attachments')
    visibility = models.CharField(max_length=10, choices=[('shared', 'Shared'), ('internal', 'Operations only')], default='shared')
    uploaded_by = models.ForeignKey(User, on_delete=models.PROTECT)
    storage_key = models.CharField(max_length=200, unique=True)
    filename = models.CharField(max_length=160)
    content_type = models.CharField(max_length=40)
    size = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']

    def save(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        old = type(self).objects.filter(pk=self.pk).first()
        if old and old.purpose != 'general' and any(
                getattr(old, f.attname) != getattr(self, f.attname) for f in self._meta.fields):
            raise ValidationError('Uploaded commercial documents are immutable.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        if self.purpose != 'general':
            raise ValidationError('Commercial documents must be retained in job history.')
        return super().delete(*args, **kwargs)


class JobComment(AppendOnlyModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(MaintenanceRequest, on_delete=models.PROTECT, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.PROTECT)
    author_name = models.CharField(max_length=300)
    author_role = models.CharField(max_length=20)
    text = models.TextField(max_length=2500)
    visibility = models.CharField(max_length=10, choices=[('shared', 'Shared'), ('internal', 'Operations only')], default='shared')
    fingerprint = models.CharField(max_length=64, blank=True)
    idempotency_key = models.UUIDField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']


class JobQuotation(models.Model):
    reference = models.CharField(max_length=80, blank=True)
    document = models.OneToOneField(MaintenanceAttachment, null=True, blank=True, on_delete=models.PROTECT, related_name='quotation')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(MaintenanceRequest, on_delete=models.PROTECT, related_name='quotations')
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='+')
    title = models.CharField(max_length=180)
    scope = models.TextField(max_length=3000)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=24, choices=[('draft', 'Draft'), ('sent', 'Sent for Approval'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('revision_requested', 'Revision Requested'), ('superseded', 'Superseded')], default='draft')
    series_id = models.UUIDField(default=uuid.uuid4, editable=False)
    revision = models.PositiveIntegerField(default=1)
    previous = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT, related_name='next_revision')
    tax_treatment = models.CharField(max_length=12, default='none')
    vat_rate = models.DecimalField(max_digits=7, decimal_places=6, default=0)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vat_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    public_snapshot = models.JSONField(default=dict)
    creation_fingerprint = models.CharField(max_length=64, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
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
            models.CheckConstraint(condition=models.Q(status__in=['draft', 'sent', 'approved', 'rejected', 'revision_requested', 'superseded']), name='quotation_valid_status'),
            models.UniqueConstraint(fields=['series_id', 'revision'], name='quotation_revision_unique'),
        ]


    def save(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        old = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        if old and old.status != 'draft':
            fields = ['reference','document_id','title','scope','amount','tax_treatment','vat_rate','subtotal','vat_total','public_snapshot','series_id','revision','previous_id','sent_at']
            if any(getattr(old, name) != getattr(self, name) for name in fields):
                raise ValidationError('Sent quotation content is immutable; create a revision.')
            if old.status == 'approved' and any(getattr(old, field.attname) != getattr(self, field.attname) for field in self._meta.fields):
                raise ValidationError('Approved quotation is immutable.')
        return super().save(*args, **kwargs)


class JobInvoice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(MaintenanceRequest, on_delete=models.PROTECT, related_name='invoices')
    document = models.OneToOneField(MaintenanceAttachment, on_delete=models.PROTECT, related_name='invoice')
    number = models.CharField(max_length=80)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField()
    visibility = models.CharField(max_length=10, choices=[('shared', 'Agency invoice'), ('internal', 'Private supplier invoice')], default='internal')
    uploaded_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    creation_key = models.UUIDField(unique=True)
    fingerprint = models.CharField(max_length=64)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=16, choices=[('unpaid','Unpaid'), ('partially_paid','Partially paid'), ('paid','Paid')], default='unpaid')
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['created_at', 'id']
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name='invoice_positive_amount'),
            models.CheckConstraint(condition=models.Q(paid_amount__gte=0) & models.Q(paid_amount__lte=models.F('amount')), name='invoice_payment_bounds'),
            models.CheckConstraint(condition=(models.Q(payment_status='unpaid', paid_amount=0) |
                models.Q(payment_status='paid', paid_amount=models.F('amount')) |
                models.Q(payment_status='partially_paid', paid_amount__gt=0, paid_amount__lt=models.F('amount'))), name='invoice_payment_state'),
            models.UniqueConstraint(fields=['request', 'visibility', 'number'], name='invoice_job_number_unique'),
        ]

    def save(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        old = type(self).objects.filter(pk=self.pk).first()
        if old and any(getattr(old, field) != getattr(self, field) for field in (
                'request_id','document_id','number','amount','due_date','visibility','uploaded_by_id','created_at','creation_key','fingerprint')):
            raise ValidationError('Invoice PDF and recorded invoice details are immutable.')
        return super().save(*args, **kwargs)


class InvoicePayment(AppendOnlyModel):
    invoice = models.ForeignKey(JobInvoice, on_delete=models.PROTECT, related_name='payments')
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_on = models.DateField()
    reference = models.CharField(max_length=180, blank=True)
    note = models.TextField(max_length=1000, blank=True)
    key = models.UUIDField(unique=True)
    fingerprint = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name='manual_payment_positive')]


class QuotationLine(models.Model):
    """Historical development rows only; current workflows do not create/calculate lines."""
    quote = models.ForeignKey(JobQuotation, on_delete=models.PROTECT, related_name='lines')
    position = models.PositiveIntegerField()
    description = models.CharField(max_length=180)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.CharField(max_length=20)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    net = models.DecimalField(max_digits=12, decimal_places=2)
    vat = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ['position']
        constraints = [models.UniqueConstraint(fields=['quote','position'],name='quotation_line_position_unique')]

    def save(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        if not JobQuotation.objects.filter(pk=self.quote_id, status='draft').exists():
            raise ValidationError('Sent quotation lines are immutable.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        if not JobQuotation.objects.filter(pk=self.quote_id, status='draft').exists():
            raise ValidationError('Sent quotation lines are immutable.')
        return super().delete(*args, **kwargs)


class QuotationPrivate(models.Model):
    quote = models.OneToOneField(JobQuotation, on_delete=models.PROTECT, related_name='private_details')
    cost_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True, max_length=3000)


class QuotationAction(AppendOnlyModel):
    quote = models.ForeignKey(JobQuotation, on_delete=models.PROTECT, related_name='actions')
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    kind = models.CharField(max_length=24)
    key = models.UUIDField(unique=True)
    fingerprint = models.CharField(max_length=64)
    reason = models.TextField(blank=True, max_length=1000)
    snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['created_at','id']


class JobActivity(AppendOnlyModel):
    class Kind(models.TextChoices):
        SUBMITTED = 'job_submitted', 'Maintenance request submitted'
        STATUS = 'status_changed', 'Status changed'
        COMMENT = 'comment_added', 'Shared comment added'
        INVOICE_UPLOADED = 'invoice_uploaded', 'Invoice PDF uploaded'
        PAYMENT_RECORDED = 'invoice_payment', 'Manual invoice payment recorded'
        QUOTE_CREATED = 'quote_created', 'Quotation draft created'
        QUOTE_EDITED = 'quote_edited', 'Quotation draft edited'
        QUOTE_SENT = 'quote_sent', 'Quotation sent for approval'
        QUOTE_REVISED = 'quote_revised', 'Quotation revision created'
        QUOTE_SUPERSEDED = 'quote_superseded', 'Quotation superseded'
        QUOTE_REVISION = 'quote_revision_requested', 'Quotation revision requested'
        CONVERSATION_PERMISSION = 'conversation_permission', 'Tenant conversation permission changed'
        INTERNAL_NOTE = 'internal_note', 'Internal Operations note'
        NOTIFICATION_STATE = 'notification_state', 'Notification state changed'
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
    visibility = models.CharField(max_length=10, default='shared')
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


class OperationsInboxItem(models.Model):
    event = models.OneToOneField(JobActivity, on_delete=models.PROTECT, related_name='inbox_item')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at','-id']


class OperationsInboxReceipt(models.Model):
    item = models.ForeignKey(OperationsInboxItem, on_delete=models.PROTECT, related_name='receipts')
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['item','user'],name='operations_inbox_receipt_unique')]
