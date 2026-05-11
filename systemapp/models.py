import os
import uuid

from django.core.exceptions import ValidationError
from django.db import models


ALLOWED_ATTACHMENT_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".png",
    ".jpg",
    ".jpeg",
}


def validate_note_attachment(file):
    extension = os.path.splitext(file.name)[1].lower()
    if extension not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise ValidationError("Only common office documents and images are allowed.")


def validate_pdf(file):
    # Backward-compatible alias kept for historical migrations.
    validate_note_attachment(file)


class Department(models.Model):
    department_name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return self.department_name

class Purpose(models.Model):
    purpose_name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.purpose_name

class NoteSheet(models.Model):
    
    PROCUREMENT_STATUS_CHOICES = (

    ('NORMAL', 'Normal Notesheet'),

    # PURCHASE FLOW
    ('PURCHASE_PENDING_CHAIRMAN', 'Pending Chairman Approval'),

    ('QUOTATION_ENTRY', 'Quotation Entry'),

    ('QUOTATION_PENDING_CHAIRMAN', 'Quotation Pending Chairman'),

    ('VENDOR_SELECTION', 'Vendor Selection'),

    ('FINAL_PENDING_CHAIRMAN', 'Final Chairman Approval'),

    ('PO_GENERATED', 'PO Generated'),

    ('FINANCE_PENDING', 'Pending Finance Approval'),

    ('PAYMENT_DONE', 'Payment Done'),

    ('INVENTORY_ENTRY', 'Inventory Entry'),

    ('CLOSED', 'Closed'),

    ('REJECTED', 'Rejected'),

    ('SENT_BACK', 'Sent Back'),
)

    notesheet_no = models.CharField(max_length=50, unique=True, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    purpose = models.ForeignKey(Purpose, on_delete=models.SET_NULL, null=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, null=True, blank=True)
    created_by = models.ForeignKey('userapp.User', on_delete=models.CASCADE, related_name='created_notesheets')
    forwarded_to = models.ForeignKey('userapp.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='received_notesheets')
    procurement_status = models.CharField(max_length=50, choices=PROCUREMENT_STATUS_CHOICES, default='NOT_STARTED')
    previous_procurement_status = models.CharField(max_length=50, choices=PROCUREMENT_STATUS_CHOICES, blank=True, default='')
    purchase_order_no = models.CharField(max_length=50, unique=True, null=True, blank=True, editable=False)
    purchase_order_file = models.FileField(upload_to='notesheets/purchase_orders/', validators=[validate_note_attachment], null=True, blank=True)
    stock_register_details = models.TextField(blank=True)
    stock_quantity = models.PositiveIntegerField(null=True, blank=True)
    stock_entry_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.notesheet_no:
            self.notesheet_no = f"NS-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def current_holder(self):
        return self.forwarded_to or self.created_by

    def is_with_user(self, user):
        if not user:
            return False

        if self.forwarded_to_id:
            return self.forwarded_to_id == user.id

        return self.created_by_id == user.id

    def can_user_edit(self, user):
        # Only the officer currently holding the file can update it.
        return self.is_with_user(user)

    def is_closed_for_workflow(self):
        return self.procurement_status in {'REJECTED', 'CLOSED'}

    def __str__(self):
        return f"{self.notesheet_no} - {self.title}"


class NoteContent(models.Model):
    notesheet = models.OneToOneField(NoteSheet, on_delete=models.CASCADE, related_name='content')
    text_content = models.TextField(blank=True)


class NoteDocument(models.Model):
    notesheet = models.ForeignKey(NoteSheet, on_delete=models.CASCADE, related_name='documents')
    file = models.FileField(upload_to='notesheets/', validators=[validate_note_attachment])
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']


class NoteRemark(models.Model):
    ACTION_CHOICES = (
        ('COMMENT', 'Comment'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('REVERT', 'Revert Back'),
        ('FORWARDED', 'Forwarded'),
    )

    notesheet = models.ForeignKey(NoteSheet, on_delete=models.CASCADE, related_name='remarks')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    remark_text = models.TextField(blank=True)
    attachment = models.FileField(upload_to='notesheets/remarks/', validators=[validate_note_attachment], null=True, blank=True)
    created_by = models.ForeignKey('userapp.User', on_delete=models.CASCADE, related_name='remarks_given')
    forwarded_to = models.ForeignKey('userapp.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='remarks_received')
    created_at = models.DateTimeField(auto_now_add=True)

    visible_to = models.ForeignKey('userapp.User',on_delete=models.SET_NULL,null=True,related_name='visible_remarks')

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.notesheet.notesheet_no} - {self.action}"


class ProcurementQuotation(models.Model):
    notesheet = models.ForeignKey(NoteSheet, on_delete=models.CASCADE, related_name='quotations')
    vendor_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    quotation_file = models.FileField(upload_to='notesheets/quotations/', validators=[validate_note_attachment], null=True, blank=True)
    uploaded_by = models.ForeignKey('userapp.User', on_delete=models.CASCADE, related_name='uploaded_quotations')
    is_l1 = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['amount', 'created_at']

    @property
    def purchase_order_no(self):
        return self.notesheet.purchase_order_no

    def __str__(self):
        return f"{self.notesheet.notesheet_no} - {self.vendor_name}"


class QuotationItem(models.Model):

    notesheet = models.ForeignKey(
        NoteSheet,
        on_delete=models.CASCADE,
        related_name='quotation_items'
    )

    item_name = models.CharField(max_length=255)

    quantity = models.PositiveIntegerField()

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):

        self.total_price = (
            self.quantity *
            self.unit_price
        )

        super().save(*args, **kwargs)


class VendorDetail(models.Model):

    notesheet = models.ForeignKey(
        NoteSheet,
        on_delete=models.CASCADE
    )

    vendor_name = models.CharField(max_length=255)

    gst_number = models.CharField(max_length=50)

    quote_price = models.CharField(blank=True,null=True)

    unit_price = models.CharField(blank=True,null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.notesheet.notesheet_no} - {self.vendor_name}"


class InventoryRegister(models.Model):

    notesheet = models.ForeignKey(
        NoteSheet,
        on_delete=models.CASCADE
    )

    item_name = models.CharField(max_length=255)

    quantity = models.PositiveIntegerField()

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    vendor_name = models.CharField(max_length=255)

    stock_entry_date = models.DateField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.item_name