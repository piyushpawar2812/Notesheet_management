from decimal import Decimal
import uuid

from django.contrib import messages
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render
)

from userapp.models import *
from systemapp.views import *
from systemapp.models import *


from .models import (
    NoteSheet,
    ProcurementQuotation,
    QuotationItem,
    VendorDetail,
    NoteRemark
)

from userapp.models import User


# =========================================================
# CHAIRMAN APPROVAL
# =========================================================

def chairman_approve_view(request, pk):

    user = get_user(request)

    note = get_object_or_404(
        NoteSheet,
        id=pk
    )

    # ONLY CHAIRMAN
    if not user.role or user.role.role_name.strip().lower() != 'chairman':

        messages.error(
            request,
            "Only chairman can approve."
        )

        return redirect(
            'edit_notesheet',
            pk=pk
        )

    # FILE MUST BE WITH CHAIRMAN
    if note.forwarded_to != user:

        messages.error(
            request,
            "File is not with chairman."
        )

        return redirect(
            'edit_notesheet',
            pk=pk
        )

    # STAGE VALIDATION
    if note.procurement_status != 'PENDING_CHAIRMAN':

        messages.error(
            request,
            "Invalid approval stage."
        )

        return redirect(
            'edit_notesheet',
            pk=pk
        )

    # APPROVE
    note.procurement_status = (
        'QUOTATIONS_UPLOAD'
    )

    # RETURN FILE TO CREATOR
    note.forwarded_to = (
        note.created_by
    )

    note.save(
        update_fields=[
            'procurement_status',
            'forwarded_to'
        ]
    )

    # REMARK
    NoteRemark.objects.create(

        notesheet=note,

        action='APPROVED',

        created_by=user,

        forwarded_to=note.created_by,

        visible_to=note.created_by,

        remark_text=(
            "Chairman approved "
            "quotation stage."
        )
    )

    messages.success(
        request,
        "Chairman approved successfully."
    )

    return redirect(
        'edit_notesheet',
        pk=pk
    )


# =========================================================
# ADD QUOTATION
# =========================================================

def add_quotation_view(request, pk):

    user = get_user(request)

    note = get_object_or_404(
        NoteSheet,
        id=pk
    )

    if request.method != 'POST':

        return redirect(
            'edit_notesheet',
            pk=pk
        )

    vendor_name = request.POST.get(
        'vendor_name'
    )

    amount = request.POST.get(
        'amount'
    )

    item_name = request.POST.get(
        'item_name'
    )

    quantity = request.POST.get(
        'quantity'
    )

    unit_price = request.POST.get(
        'unit_price'
    )

    quotation_file = request.FILES.get(
        'quotation_file'
    )

    quotation = ProcurementQuotation.objects.create(

        notesheet=note,

        vendor_name=vendor_name,

        amount=Decimal(amount),

        quotation_file=quotation_file,

        uploaded_by=user
    )

    QuotationItem.objects.create(

        quotation=quotation,

        item_name=item_name,

        quantity=quantity,

        unit_price=Decimal(unit_price),

        total_price=(
            Decimal(quantity) *
            Decimal(unit_price)
        )
    )

    # MOVE NEXT STAGE
    note.procurement_status = (
        'VENDOR_UPLOAD'
    )

    note.save(
        update_fields=['procurement_status']
    )

    NoteRemark.objects.create(

        notesheet=note,

        action='COMMENT',

        created_by=user,

        visible_to=user,

        remark_text=(
            f"Quotation uploaded "
            f"for {vendor_name}"
        )
    )

    messages.success(
        request,
        "Quotation added successfully."
    )

    return redirect(
        'edit_notesheet',
        pk=pk
    )


# =========================================================
# ADD VENDOR
# =========================================================

def add_vendor_view(request, pk):

    user = get_user(request)

    note = get_object_or_404(
        NoteSheet,
        id=pk
    )

    if request.method != 'POST':

        return redirect(
            'edit_notesheet',
            pk=pk
        )

    VendorDetail.objects.create(

        notesheet=note,

        vendor_name=request.POST.get(
            'vendor_name'
        ),

        gst_number=request.POST.get(
            'gst_number'
        ),

        quote_price=request.POST.get(
            'quote_price'
        ),

        unit_price=request.POST.get(
            'unit_price'
        ),

        contact_person=request.POST.get(
            'contact_person'
        ),

        contact_email=request.POST.get(
            'contact_email'
        ),

        contact_phone=request.POST.get(
            'contact_phone'
        ),

        address=request.POST.get(
            'address'
        ),

        uploaded_by=user
    )

    # NOW AGAIN CHAIRMAN APPROVAL
    note.procurement_status = (
        'PENDING_FINAL_APPROVAL'
    )

    note.save(
        update_fields=['procurement_status']
    )

    messages.success(
        request,
        "Vendor detail uploaded."
    )

    return redirect(
        'edit_notesheet',
        pk=pk
    )


# =========================================================
# FINAL APPROVAL
# =========================================================

def final_approve_view(request, pk):

    user = get_user(request)

    note = get_object_or_404(
        NoteSheet,
        id=pk
    )

    if not user.role or user.role.role_name.strip().lower() != 'chairman':

        messages.error(
            request,
            "Only chairman can approve."
        )

        return redirect(
            'edit_notesheet',
            pk=pk
        )

    # GENERATE PO
    note.purchase_order_no = (
        f"PO-{uuid.uuid4().hex[:8].upper()}"
    )

    note.procurement_status = (
        'PENDING_PAYMENT'
    )

    note.forwarded_to = (
        note.created_by
    )

    note.save(
        update_fields=[
            'purchase_order_no',
            'procurement_status',
            'forwarded_to'
        ]
    )

    NoteRemark.objects.create(

        notesheet=note,

        action='APPROVED',

        created_by=user,

        visible_to=note.created_by,

        forwarded_to=note.created_by,

        remark_text=(
            "Final approval completed."
        )
    )

    messages.success(
        request,
        "Final approval completed."
    )

    return redirect(
        'edit_notesheet',
        pk=pk
    )


# =========================================================
# FINANCE APPROVAL
# =========================================================

def finance_approve_view(request, pk):

    user = get_user(request)

    note = get_object_or_404(
        NoteSheet,
        id=pk
    )

    if user.role.role_name.upper() != 'FINANCE':

        messages.error(
            request,
            "Only finance can approve."
        )

        return redirect(
            'edit_notesheet',
            pk=pk
        )

    note.procurement_status = (
        'STOCK_REGISTER'
    )

    note.save(
        update_fields=['procurement_status']
    )

    messages.success(
        request,
        "Finance approved payment."
    )

    return redirect(
        'edit_notesheet',
        pk=pk
    )


# =========================================================
# STOCK ENTRY
# =========================================================

def stock_entry_view(request, pk):

    user = get_user(request)

    note = get_object_or_404(
        NoteSheet,
        id=pk
    )

    note.stock_register_details = (
        request.POST.get(
            'stock_details'
        )
    )

    note.stock_quantity = (
        request.POST.get(
            'stock_quantity'
        )
    )

    note.stock_entry_date = (
        request.POST.get(
            'stock_date'
        )
    )

    note.procurement_status = (
        'CLOSED'
    )

    note.save(
        update_fields=[
            'stock_register_details',
            'stock_quantity',
            'stock_entry_date',
            'procurement_status'
        ]
    )

    messages.success(
        request,
        "Stock register completed."
    )

    return redirect(
        'edit_notesheet',
        pk=pk
    )