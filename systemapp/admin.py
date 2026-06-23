from django.contrib import admin

from userapp.models import (
    User,
    RoleMaster
)

from systemapp.models import (
    Department,
Collage,
    Purpose,
    NoteSheet,
    NoteRemark,
    VendorQuotationItem,
    VendorQuotation,
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


@admin.register(Collage)
class CollageAdmin(admin.ModelAdmin):

    list_display = (
        'collage_name',
        'collage_code',
    )

    search_fields = (
        'collage_name',
         'collage_code',
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

# =========================================================
# QUOTATION ITEM INLINE
# =========================================================

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
# =========================================================
# NOTE CONTENT ADMIN
# =========================================================



# =========================================================
# NOTE DOCUMENT ADMIN
# =========================================================
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
# =========================================================
# QUOTATION ITEM ADMIN
# =========================================================


@admin.register(VendorQuotation)
class VendorQuotation(admin.ModelAdmin):

    list_display = (
        'vendor_name',
        'is_winner',
        'gst_number',
        'total_amount',

    )

    search_fields = (
        'vendor_name',
        'is_winner',
        'gst_number',
        'total_amount',
    )


@admin.register(VendorQuotationItem)
class VendorQuotationItem(admin.ModelAdmin):

    list_display = (
        'quotation',
        'item_name',
        'quotation_price',
        'created_at',

    )

    search_fields = (
        'item_name',
    )



# =======================================================

# =========================================================
# INVENTORY REGISTER ADMIN
# =========================================================
