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
    # Nullable for historical addresses: never guess a structured location.
    city = models.ForeignKey('City', null=True, blank=True, on_delete=models.PROTECT)
    suburb = models.ForeignKey('Suburb', null=True, blank=True, on_delete=models.PROTECT)

    def clean(self):
        super().clean()
        if self.suburb_id and (not self.city_id or self.suburb.city_id != self.city_id):
            from django.core.exceptions import ValidationError
            raise ValidationError({'suburb': 'Suburb must belong to the selected city.'})

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)
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
    purpose = models.CharField(max_length=12, default='general', choices=[('general', 'Job attachment'), ('quotation', 'Quotation PDF'), ('invoice', 'Invoice PDF'), ('credit_note', 'External credit note PDF')])
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
    record_number = models.CharField(max_length=24, unique=True, null=True, blank=True)
    amends = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='amendments')
    amendment_reason = models.TextField(max_length=1000, blank=True)
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
            fields = ['record_number','amends_id','amendment_reason','reference','document_id','title','scope','amount','tax_treatment','vat_rate','subtotal','vat_total','public_snapshot','series_id','revision','previous_id','sent_at']
            if any(getattr(old, name) != getattr(self, name) for name in fields):
                raise ValidationError('Sent quotation content is immutable; create a revision.')
            if old.status == 'approved' and any(getattr(old, field.attname) != getattr(self, field.attname) for field in self._meta.fields):
                raise ValidationError('Approved quotation is immutable.')
        return super().save(*args, **kwargs)


class JobInvoice(models.Model):
    record_number = models.CharField(max_length=24, unique=True, null=True, blank=True)
    previous = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT, related_name='replacement')
    correction_reason = models.TextField(max_length=1000, blank=True)
    refunded_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    document_status = models.CharField(max_length=10, default='active', choices=[('active','Active'),('void','Void')])
    void_reason = models.TextField(max_length=1000, blank=True)
    voided_on = models.DateField(null=True, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    accounting_reference = models.CharField(max_length=180, blank=True)
    reconciliation_required = models.BooleanField(default=False)
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
    payment_status = models.CharField(max_length=16, choices=[('unpaid','Unpaid'), ('partially_paid','Partially paid'), ('paid','Paid'), ('refunded','Fully refunded')], default='unpaid')
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['created_at', 'id']
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name='invoice_positive_amount'),
            models.CheckConstraint(condition=models.Q(paid_amount__gte=models.F('refunded_amount')) & models.Q(refunded_amount__gte=0) & models.Q(paid_amount__lte=models.F('amount')+models.F('refunded_amount')), name='invoice_payment_bounds'),
            models.CheckConstraint(condition=(models.Q(payment_status='unpaid', paid_amount=0, refunded_amount=0) |
                models.Q(payment_status='refunded', paid_amount__gt=0, paid_amount=models.F('refunded_amount')) |
                models.Q(payment_status='paid', paid_amount=models.F('amount')+models.F('refunded_amount')) |
                models.Q(payment_status='partially_paid', paid_amount__gt=models.F('refunded_amount'), paid_amount__lt=models.F('amount')+models.F('refunded_amount'))), name='invoice_payment_state'),
            models.CheckConstraint(condition=models.Q(document_status__in=['active','void']), name='invoice_document_state'),
            models.UniqueConstraint(fields=['request', 'visibility', 'number'], name='invoice_job_number_unique'),
        ]

    def save(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        old = type(self).objects.filter(pk=self.pk).first()
        if old and any(getattr(old, field) != getattr(self, field) for field in (
                'record_number','previous_id','correction_reason','request_id','document_id','number','amount','due_date','visibility','uploaded_by_id','created_at','creation_key','fingerprint')):
            raise ValidationError('Invoice PDF and recorded invoice details are immutable.')
        if old and old.document_status == 'void' and any(getattr(old, f) != getattr(self, f) for f in (
                'document_status','void_reason','voided_on','voided_at','voided_by_id','accounting_reference')):
            raise ValidationError('Void records cannot be rewritten or reopened.')
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


class InvoiceRefund(AppendOnlyModel):
    invoice = models.ForeignKey(JobInvoice, on_delete=models.PROTECT, related_name='refunds')
    payment = models.ForeignKey(InvoicePayment, on_delete=models.PROTECT, related_name='refunds')
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    refunded_on = models.DateField()
    reason = models.TextField(max_length=1000)
    reference = models.CharField(max_length=180)
    key = models.UUIDField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at','id']
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name='refund_positive')]


class InvoiceAction(AppendOnlyModel):
    invoice = models.ForeignKey(JobInvoice, on_delete=models.PROTECT, related_name='actions')
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    kind = models.CharField(max_length=24)
    key = models.UUIDField(unique=True)
    fingerprint = models.CharField(max_length=64)
    reason = models.TextField(max_length=1000, blank=True)
    reference = models.CharField(max_length=180, blank=True)
    snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at','id']


class InvoiceCreditNote(AppendOnlyModel):
    invoice = models.ForeignKey(JobInvoice, on_delete=models.PROTECT, related_name='credit_notes')
    document = models.OneToOneField(MaintenanceAttachment, on_delete=models.PROTECT)
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    reference = models.CharField(max_length=80)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    issued_on = models.DateField()
    reason = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)


class QuoteApprovalReplacement(AppendOnlyModel):
    original = models.OneToOneField(JobQuotation, on_delete=models.PROTECT, related_name='approval_replacement')
    replacement = models.OneToOneField(JobQuotation, on_delete=models.PROTECT, related_name='replaces_approval')
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class DocumentSequence(models.Model):
    prefix = models.CharField(max_length=2, choices=[('SQ','Quotation'),('SI','Invoice')])
    year = models.PositiveIntegerField()
    last_value = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['prefix','year'], name='document_annual_sequence')]


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
        ASSIGNED = 'job_assigned', 'Private subcontractor assignment recorded'
        SUBMITTED = 'job_submitted', 'Maintenance request submitted'
        STATUS = 'status_changed', 'Status changed'
        COMMENT = 'comment_added', 'Shared comment added'
        INVOICE_REFUND = 'invoice_refund', 'Manual refund recorded'
        INVOICE_VOID = 'invoice_void', 'Invoice voided'
        INVOICE_CORRECTED = 'invoice_corrected', 'Replacement invoice uploaded'
        INVOICE_RECONCILED = 'invoice_reconciled', 'Invoice reconciliation recorded'
        CREDIT_NOTE = 'invoice_credit_note', 'External credit note uploaded'
        QUOTE_AMENDED = 'quote_amended', 'Quotation amendment requested'
        QUOTE_EFFECTIVE = 'quote_amendment_active', 'Approved amendment replaces prior approval'
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
    retry_limit = models.PositiveIntegerField(default=5)
    feedback_status = models.CharField(max_length=16, default='unknown')
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


class OperationsFeedback(AppendOnlyModel):
    notification = models.ForeignKey(OperationsNotification, on_delete=models.PROTECT, related_name='feedback')
    provider_event_id = models.CharField(max_length=180, unique=True)
    kind = models.CharField(max_length=16, choices=[('delivered','Delivered'),('bounce','Bounce'),('complaint','Complaint')])
    occurred_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)


class OperationsReplay(AppendOnlyModel):
    notification = models.ForeignKey(OperationsNotification, on_delete=models.PROTECT, related_name='replays')
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    reason = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)


class OperationsWorkerHeartbeat(models.Model):
    name = models.CharField(max_length=40, primary_key=True)
    at = models.DateTimeField(default=timezone.now)


class OperationsFeedbackResolution(AppendOnlyModel):
    feedback = models.OneToOneField(OperationsFeedback, on_delete=models.PROTECT, related_name='resolution')
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    reason = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)


class Province(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class City(models.Model):
    province = models.ForeignKey(Province, on_delete=models.PROTECT, related_name='cities')
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ['name', 'id']
        constraints = [models.UniqueConstraint(Lower('name'), 'province', name='city_name_per_province')]

    def __str__(self):
        return f'{self.name}, {self.province.name}'


class Suburb(models.Model):
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name='suburbs')
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ['name', 'id']
        constraints = [models.UniqueConstraint(Lower('name'), 'city', name='suburb_name_per_city')]

    def __str__(self):
        return f'{self.name}, {self.city.name}'


class Subcontractor(models.Model):
    """Private Operations directory; never serialized into agency/tenant job data."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=180)
    active = models.BooleanField(default=True)
    provinces = models.ManyToManyField(Province, blank=True, related_name='subcontractors')
    cities = models.ManyToManyField(City, blank=True, related_name='subcontractors')
    suburbs = models.ManyToManyField(Suburb, blank=True, related_name='subcontractors')
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name', 'id']


class JobAssignment(AppendOnlyModel):
    request = models.ForeignKey(MaintenanceRequest, on_delete=models.PROTECT, related_name='assignments')
    subcontractor = models.ForeignKey(Subcontractor, on_delete=models.PROTECT)
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    submission_key = models.UUIDField(unique=True)
    # Preserve the location reviewed at assignment time if a property moves later.
    city = models.ForeignKey(City, on_delete=models.PROTECT)
    suburb = models.ForeignKey(Suburb, null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        ordering = ['-created_at', '-id']
