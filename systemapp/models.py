import os
import uuid

from django.utils import timezone

from django.core.exceptions import ValidationError
from django.db import models

from decimal import Decimal

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
    
class Collage(models.Model):
    collage_name = models.CharField(max_length=50, unique=True)
    collage_code = models.CharField(max_length=20, unique=True,blank=True,null=True)

    def __str__(self):
        return self.collage_name

class NoteSheet(models.Model):
    
    PROCUREMENT_STATUS_CHOICES = (

    ('NORMAL', 'Normal'),

    ('PURCHASE_PENDING_CHAIRMAN', 'Pending Chairman Approval'),

    ('QUOTATION_ENTRY', 'Quotation Entry'),

    ('QUOTATION_PENDING_CHAIRMAN', 'Quotation Pending Chairman'),

    ('QUOTATION_REVERTED', 'Quotation Reverted'),

    ('PO_PENDING', 'PO Pending'),

    ('PO_GENERATED', 'PO Generated'),

    ('INVENTORY_ENTRY', 'Inventory Entry'),

    ('FINANCE_REVIEW', 'Finance Review'),

    ('BILL_PENDING_CHAIRMAN', 'Bill Pending Chairman'),

    ('FINAL_FINANCE_APPROVAL', 'Final Finance Approval'),

    ('CLOSED', 'Closed'),

    ('REJECTED', 'Rejected'),
)
    GENERAL_STATUS_CHOICE=[('PENDING', 'Pending'),

    ('APPROVED', 'Approved'),

    ('REJECTED', 'Rejected'),]

    notesheet_no = models.CharField(max_length=50, unique=True, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    collage=models.ForeignKey(Collage, on_delete=models.CASCADE, null=True, blank=True)
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
    po_pdf = models.FileField(upload_to='purchase_orders/',null=True,blank=True)
    finance_attachment = models.FileField(upload_to='notesheets/finance_attachments/',null=True,blank=True)
    general_status = models.CharField(max_length=50, choices=GENERAL_STATUS_CHOICE, default='PENDING')
    approved_by = models.ForeignKey('userapp.User',null=True,blank=True,on_delete=models.SET_NULL)
    is_deleted = models.BooleanField(default=False)

    
    class Meta:
        ordering = ['-created_at']

    
    def save(self, *args, **kwargs):
        if not self.notesheet_no:
            college_code = self.created_by.collage.collage_code
            year = timezone.now().year

            last_note = NoteSheet.objects.filter(
                notesheet_no__startswith=f"{college_code}/{year}/"
            ).order_by("-id").first()

            if last_note:
                sequence = int(last_note.notesheet_no.split("/")[-1]) + 1
            else:
                sequence = 1

            self.notesheet_no = f"{college_code}/{year}/{sequence:04d}"

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
    general_status = models.CharField(max_length=50, choices=NoteSheet.GENERAL_STATUS_CHOICE, default='PENDING',null=True,blank=True)
    approved_by = models.ForeignKey('userapp.User',null=True,blank=True,on_delete=models.SET_NULL)


    visible_to = models.ForeignKey('userapp.User',on_delete=models.SET_NULL,null=True,related_name='visible_remarks')

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.notesheet.notesheet_no} - {self.action}"


from decimal import Decimal

class VendorQuotation(models.Model):

    notesheet = models.ForeignKey(
        'NoteSheet',
        on_delete=models.CASCADE,
        related_name='vendors'
    )

    vendor_name = models.CharField(
        max_length=255
    )

    gst_number = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    address = models.TextField(
        blank=True,
        null=True
    )

    quotation_file = models.FileField(
        upload_to='notesheets/quotations/',
        null=True,
        blank=True
    )

    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    is_winner = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):

        return self.vendor_name


class VendorQuotationItem(models.Model):

    quotation = models.ForeignKey(
        VendorQuotation,
        on_delete=models.CASCADE,
        related_name='items'
    )

    item_name = models.CharField(
        max_length=255
    )

    quantity = models.IntegerField()

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    quotation_price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def save(self, *args, **kwargs):

        self.total_price = (
            Decimal(self.quantity)
            * Decimal(self.quotation_price)
        )

        super().save(*args, **kwargs)


    
class PurchaseOrder(models.Model):

    notesheet = models.OneToOneField(

        NoteSheet,

        on_delete=models.CASCADE,

        related_name='purchase_order'

    )

    vendor = models.ForeignKey(

        VendorQuotation,

        on_delete=models.CASCADE,

        related_name='purchase_orders', blank=True,
        null=True

    )

    po_number = models.CharField(

        max_length=100,

        unique=True

    )

    total_amount = models.DecimalField(

        max_digits=12,

        decimal_places=2

    )

    po_file = models.FileField(

        upload_to='purchase_orders/'

    )

    created_by = models.ForeignKey(

        'userapp.User',

        on_delete=models.CASCADE

    )

    created_at = models.DateTimeField(

        auto_now_add=True

    )

    def __str__(self):

        return self.po_number

class InventoryItem(models.Model):

    category = models.CharField(max_length=255,blank=True, null=True)

    item_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=0)

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )

    description = models.TextField(blank=True, null=True)

    supplier_name = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    added_date = models.DateField(null=True,blank=True)

    is_available = models.BooleanField(default=True)
    
    notesheet = models.ForeignKey(
    NoteSheet,
    on_delete=models.CASCADE,
    null=True,
    blank=True
)

    def __str__(self):
        return self.item_name
    
    
    
    

