from django.contrib import admin

from userapp.models import (
    User,
    RoleMaster
)

from systemapp.models import (
    Department,
    Purpose,
    NoteSheet,
    NoteContent,
    NoteDocument,
    NoteRemark,
    ProcurementQuotation,
    QuotationItem,
    VendorDetail,
    InventoryRegister
)


# =========================================================
# USER ADMIN
# =========================================================

@admin.register(User)
class UserAdmin(admin.ModelAdmin):

    list_display = (
        'officer_name',
        'login_id',
        'role',
        'department',
        'designation',
    )

    search_fields = (
        'officer_name',
        'login_id',
        'designation',
    )

    list_filter = (
        'role',
        'department',
    )


# =========================================================
# ROLE ADMIN
# =========================================================

@admin.register(RoleMaster)
class RoleMasterAdmin(admin.ModelAdmin):

    list_display = (
        'role_name',
    )


# =========================================================
# DEPARTMENT ADMIN
# =========================================================

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):

    list_display = (
        'department_name',
        'created_at',
        'is_deleted',
    )

    search_fields = (
        'department_name',
    )


# =========================================================
# PURPOSE ADMIN
# =========================================================

@admin.register(Purpose)
class PurposeAdmin(admin.ModelAdmin):

    list_display = (
        'purpose_name',
    )

    search_fields = (
        'purpose_name',
    )


# =========================================================
# NOTE DOCUMENT INLINE
# =========================================================

class NoteDocumentInline(admin.TabularInline):

    model = NoteDocument

    extra = 1


# =========================================================
# QUOTATION ITEM INLINE
# =========================================================

class QuotationItemInline(admin.TabularInline):

    model = QuotationItem

    extra = 1

    fields = (
        'item_name',
        'quantity',
        'unit_price',
        'total_price',
    )

    readonly_fields = (
        'total_price',
    )


# =========================================================
# VENDOR DETAIL INLINE
# =========================================================

class VendorDetailInline(admin.TabularInline):

    model = VendorDetail

    extra = 1


# =========================================================
# NOTESHEET ADMIN
# =========================================================

@admin.register(NoteSheet)
class NoteSheetAdmin(admin.ModelAdmin):

    list_display = (
        'notesheet_no',
        'title',
        'purpose',
        'procurement_status',
        'created_by',
        'forwarded_to',
        'created_at',
    )

    search_fields = (
        'notesheet_no',
        'title',
    )

    list_filter = (
        'purpose',
        'procurement_status',
        'created_at',
    )

    readonly_fields = (
        'notesheet_no',
        'purchase_order_no',
    )

    inlines = [
        NoteDocumentInline,
        QuotationItemInline,
        VendorDetailInline,
    ]


# =========================================================
# NOTE CONTENT ADMIN
# =========================================================

@admin.register(NoteContent)
class NoteContentAdmin(admin.ModelAdmin):

    list_display = (
        'notesheet',
    )


# =========================================================
# NOTE DOCUMENT ADMIN
# =========================================================

@admin.register(NoteDocument)
class NoteDocumentAdmin(admin.ModelAdmin):

    list_display = (
        'notesheet',
        'uploaded_at',
    )

    search_fields = (
        'notesheet__notesheet_no',
    )


# =========================================================
# NOTE REMARK ADMIN
# =========================================================

@admin.register(NoteRemark)
class NoteRemarkAdmin(admin.ModelAdmin):

    list_display = (
        'notesheet',
        'action',
        'created_by',
        'forwarded_to',
        'created_at',
    )

    search_fields = (
        'notesheet__notesheet_no',
        'remark_text',
    )

    list_filter = (
        'action',
        'created_at',
    )


# =========================================================
# PROCUREMENT QUOTATION ADMIN
# =========================================================

@admin.register(ProcurementQuotation)
class ProcurementQuotationAdmin(admin.ModelAdmin):

    list_display = (
        'notesheet',
        'vendor_name',
        'amount',
        'is_l1',
        'uploaded_by',
        'created_at',
    )

    search_fields = (
        'vendor_name',
        'notesheet__notesheet_no',
    )

    list_filter = (
        'is_l1',
        'created_at',
    )


# =========================================================
# QUOTATION ITEM ADMIN
# =========================================================

@admin.register(QuotationItem)
class QuotationItemAdmin(admin.ModelAdmin):

    list_display = (
        'notesheet',
        'item_name',
        'quantity',
        'unit_price',
        'total_price',
        'created_at',
    )

    search_fields = (
        'item_name',
        'notesheet__notesheet_no',
    )


# =========================================================
# VENDOR DETAIL ADMIN
# =========================================================

@admin.register(VendorDetail)
class VendorDetailAdmin(admin.ModelAdmin):

    list_display = (
        'notesheet',
        'vendor_name',
        'gst_number',
        'quote_price',
        'unit_price',
        'created_at',
    )

    search_fields = (
        'vendor_name',
        'notesheet__notesheet_no',
    )


# =========================================================
# INVENTORY REGISTER ADMIN
# =========================================================

@admin.register(InventoryRegister)
class InventoryRegisterAdmin(admin.ModelAdmin):

    list_display = (
        'notesheet',
        'item_name',
        'quantity',
        'unit_price',
        'vendor_name',
        'stock_entry_date',
    )

    search_fields = (
        'item_name',
        'vendor_name',
        'notesheet__notesheet_no',
    )

    list_filter = (
        'stock_entry_date',
    )