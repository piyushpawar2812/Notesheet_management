import io

from datetime import date

from decimal import Decimal

from django.core.files.base import ContentFile

from reportlab.pdfgen import canvas
import uuid
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.core.files.base import ContentFile
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from reportlab.pdfgen import canvas

from userapp.models import User
from userapp.views import get_session_user

from .models import Department, NoteContent, NoteDocument, NoteRemark, NoteSheet, ProcurementQuotation,Purpose
from .models import *

PROCUREMENT_STATUS_LABELS = dict(NoteSheet.PROCUREMENT_STATUS_CHOICES)


def get_user(request):
    return User.objects.filter(id=request.session.get('user_id'), is_deleted=False, status=True).first()


def get_role_key(user):
    if not user:
        return ""
    role_name = user.role.role_name.lower() if user.role_id and user.role.role_name else ""
    return f"{user.login_id.lower()} {role_name} {user.designation.lower()}"


def is_creator_admin(user, note):
    return bool(user and note.created_by_id == user.id)


def is_director_user(user):
    role_key = get_role_key(user)
    return "director" in role_key


def is_chairman_user(user):
    role_key = get_role_key(user)
    return "chairman" in role_key


def is_finance_user(user):
    role_key = get_role_key(user)
    return "finance" in role_key


def is_hod_user(user):
    role_key = get_role_key(user)
    return "hod" in role_key


def get_accessible_notes_queryset(user):
    return (
        NoteSheet.objects.filter(
            Q(created_by=user)
            | Q(forwarded_to=user)
            | Q(remarks__created_by=user)
            | Q(remarks__forwarded_to=user)
        )
        .select_related('department', 'created_by', 'forwarded_to')
        .prefetch_related('documents', 'remarks__created_by', 'remarks__forwarded_to', 'quotations__uploaded_by')
        .distinct()
    )


def get_note_for_user(user, pk):
    return get_object_or_404(get_accessible_notes_queryset(user), pk=pk)


def find_workflow_user(*keywords):
    for keyword in keywords:
        exact_match = User.objects.filter(
            is_deleted=False,
            status=True,
        ).filter(
            Q(login_id__iexact=keyword)
            | Q(role__role_name__iexact=keyword)
            | Q(designation__iexact=keyword)
            | Q(officer_name__iexact=keyword)
        ).first()
        if exact_match:
            return exact_match

        partial_match = User.objects.filter(
            is_deleted=False,
            status=True,
        ).filter(
            Q(login_id__icontains=keyword)
            | Q(role__role_name__icontains=keyword)
            | Q(designation__icontains=keyword)
            | Q(officer_name__icontains=keyword)
        ).first()
        if partial_match:
            return partial_match
    return None


def get_director_user():
    return find_workflow_user("director")


def get_chairman_user():
    return find_workflow_user("chairman")


def get_finance_user():
    return find_workflow_user("finance")


def add_workflow_remark(
    notesheet,
    user,
    action,
    text='',
    attachment=None,
    forwarded_to=None
):

    NoteRemark.objects.create(

        notesheet=notesheet,

        created_by=user,

        action=action,

        remark_text=text,

        attachment=attachment,

        forwarded_to=forwarded_to
    )



def build_timeline(note):
    timeline = note.remarks.select_related('created_by', 'forwarded_to').all()
    if note.description:
        timeline = timeline.exclude(
            action='COMMENT',
            created_by=note.created_by,
            remark_text=note.description,
            attachment='',
        )

    timeline_events = []
    for remark in timeline:
        timeline_events.append({
            'event_type': 'remark',
            'created_at': remark.created_at,
            'created_by': remark.created_by,
            'forwarded_to': remark.forwarded_to,
            'label': remark.get_action_display(),
            'remark_text': remark.remark_text,
            'attachment': getattr(remark, 'attachment', None),
            'attachment_full_url': getattr(remark, 'attachment_full_url', ''),
            'attachment_name': remark.attachment.name.replace('notesheets/remarks/', '') if remark.attachment else '',
        })

    for document in note.documents.all():
        timeline_events.append({
            'event_type': 'document',
            'created_at': document.uploaded_at,
            'created_by': note.created_by,
            'forwarded_to': None,
            'label': 'Attachment',
            'remark_text': '',
            'attachment': document.file,
            'attachment_full_url': getattr(document, 'full_url', ''),
            'attachment_name': document.file.name.replace('notesheets/', ''),
        })

    timeline_events.sort(key=lambda item: item['created_at'])
    return timeline_events




def create_notesheet(request):
    user = get_session_user(request)
    if not user:
        return redirect('login')

    departments = Department.objects.filter(is_deleted=False).order_by('department_name')
    purpose = Purpose.objects.all().order_by('purpose_name')

    if request.method == "POST":
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        dept_id = request.POST.get('department')
        purpose_id = request.POST.get('purpose')

        if not title:
            messages.error(request, "Title is required.")
            return redirect('create_notesheet')

        department = Department.objects.filter(id=dept_id).first() if dept_id else None
        purpose = Purpose.objects.filter(id=purpose_id).first() if purpose_id else None
        note = NoteSheet.objects.create(
            title=title,
            description=description,
            department=department,
            purpose=purpose,
            created_by=user
        )

        messages.success(request, "Notesheet created successfully.")
        return redirect('edit_notesheet', pk=note.id)

    return render(request, 'services/create_notesheet.html', {'departments': departments,'purpose':purpose})


def your_notesheets(request):
    user = get_session_user(request)
    if not user:
        return redirect('login')

    notes = []
    for note in get_accessible_notes_queryset(user):
        notes.append({
            'instance': note,
            'can_edit': note.can_user_edit(user),
            'current_holder': note.current_holder(),
        })
    return render(request, 'services/your_notesheets.html', {'notes': notes})



# =========================================================
# OPEN NOTESHEET
# =========================================================

def edit_notesheet(request, pk):

    user = get_user(request)

    if not user:
        return redirect('login')

    note = get_note_for_user(user, pk)

    if request.method == "POST":

        return handle_post(
            request,
            note,
            user
        )

    context = build_note_context(
        note,
        user
    )

    return render(
        request,
        'services/note_file.html',
        context
    )

def handle_post(request, note, user):

    if note.is_closed_for_workflow():

        messages.error(
            request,
            "Workflow closed."
        )

        return redirect(
            'edit_notesheet',
            pk=note.id
        )

    if not note.can_user_edit(user):

        messages.error(
            request,
            "File is currently with another officer."
        )

        return redirect(
            'edit_notesheet',
            pk=note.id
        )

    action_type = request.POST.get(
        'action_type'
    )

    # =========================================
    # SAVE NOTE
    # =========================================

    if action_type == 'save':

        save_note_content(
            request,
            note,
            user
        )

        return redirect(
            'edit_notesheet',
            pk=note.id
        )

    # =========================================
    # NORMAL FORWARD
    # =========================================

    elif action_type == 'send':

        forward_note(
            request,
            note,
            user
        )

        return redirect(
            'edit_notesheet',
            pk=note.id
        )

    # =========================================
    # CHAIRMAN PURCHASE APPROVAL
    # =========================================

    elif action_type == 'chairman_purchase_approve':

        return chairman_purchase_approve(
            request,
            note.id
        )

    # =========================================
    # QUOTATION APPROVAL
    # =========================================

    elif action_type == 'chairman_quotation_approve':

        return chairman_quotation_approve(
            request,
            note.id
        )

    # =========================================
    # FINAL APPROVAL
    # =========================================

    elif action_type == 'chairman_final_approve':

        return chairman_final_approve(
            request,
            note.id
        )

    # =========================================
    # FINANCE APPROVAL
    # =========================================

    elif action_type == 'finance_payment_approve':

        return finance_payment_approve(
            request,
            note.id
        )

    # =========================================
    # CLOSE INVENTORY
    # =========================================

    elif action_type == 'close_inventory':

        return close_inventory(
            request,
            note.id
        )

    # =========================================
    # INVALID ACTION
    # =========================================

    messages.error(
        request,
        "Invalid action."
    )

    return redirect(
        'edit_notesheet',
        pk=note.id
    )

# =========================================================
# SAVE NOTE CONTENT
# =========================================================

def save_note_content(request, note, user):

    text = request.POST.get(
        'content',
        ''
    ).strip()

    attachment = request.FILES.get(
        'remark_attachment'
    )

    if not text and not attachment:

        messages.warning(
            request,
            "Write note or upload attachment."
        )

        return

    # ==========================================
    # SAVE REMARK
    # ==========================================

    NoteRemark.objects.create(

        notesheet=note,

        created_by=user,

        action='COMMENT',

        remark_text=text,

        attachment=attachment,

        visible_to=user
    )

    messages.success(
        request,
        "Note added successfully."
    )

# =========================================================
# FORWARD FILE
# =========================================================

def forward_note(request, note, user):

    forwarded_to_id = request.POST.get(
        'forwarded_to'
    )

    # =====================================================
    # VALIDATION
    # =====================================================

    if not forwarded_to_id:

        messages.error(
            request,
            "Select officer before forwarding."
        )

        return redirect(
            'edit_notesheet',
            pk=note.id
        )

    forwarded_user = User.objects.filter(

        id=forwarded_to_id,

        is_deleted=False,

        status=True

    ).first()

    if not forwarded_user:

        messages.error(
            request,
            "Invalid officer selected."
        )

        return redirect(
            'edit_notesheet',
            pk=note.id
        )

    if forwarded_user.id == user.id:

        messages.error(
            request,
            "Cannot forward to yourself."
        )

        return redirect('edit_notesheet',pk=note.id)

    # =====================================================
    # ROLE CHECK
    # =====================================================

    role_name = ''

    if (
        forwarded_user.role
        and forwarded_user.role.role_name
    ):

        role_name = (
            forwarded_user.role.role_name
            .strip()
            .lower()
        )

    # =====================================================
    # PROCUREMENT STATUS UPDATE
    # =====================================================

    if (
        note.purpose
        and note.purpose.purpose_name
        and note.purpose.purpose_name.lower() == "purchase"
    ):

        if role_name == "chairman":

            note.procurement_status = (
                'PURCHASE_PENDING_CHAIRMAN'
            )

    # =====================================================
    # GET CURRENT FILE SNAPSHOT
    # =====================================================

    current_remarks = NoteRemark.objects.filter(

        notesheet=note,

        visible_to=user

    ).order_by('created_at')

    # =====================================================
    # REMOVE OLD SNAPSHOT OF NEXT USER
    # =====================================================

    NoteRemark.objects.filter(

        notesheet=note,

        visible_to=forwarded_user

    ).delete()

    # =====================================================
    # COPY FILE TO NEXT USER
    # =====================================================

    for old in current_remarks:

        new_remark = NoteRemark.objects.create(

            notesheet=note,

            created_by=old.created_by,

            action=old.action,

            remark_text=old.remark_text,

            attachment=old.attachment,

            forwarded_to=old.forwarded_to,

            visible_to=forwarded_user
        )

        # Preserve original timestamp

        new_remark.created_at = old.created_at

        new_remark.save(
            update_fields=['created_at']
        )

    # =====================================================
    # MOVE FILE
    # =====================================================

    note.forwarded_to = forwarded_user

    note.save(
        update_fields=[
            'forwarded_to',
            'procurement_status'
        ]
    )

    # =====================================================
    # WORKFLOW REMARK
    # =====================================================

    NoteRemark.objects.create(

        notesheet=note,

        created_by=user,

        forwarded_to=forwarded_user,

        action='FORWARDED',

        remark_text=(
            f"File forwarded to "
            f"{forwarded_user.officer_name}"
        ),

        visible_to=forwarded_user
    )

    # =====================================================
    # SUCCESS MESSAGE
    # =====================================================

    messages.success(

        request,

        f"Notesheet forwarded to "
        f"{forwarded_user.officer_name}."
    )

    # =====================================================
    # RETURN RESPONSE
    # =====================================================

    return redirect(
        'edit_notesheet',
        pk=note.id
    )

def build_note_context(note, user):

    remarks = NoteRemark.objects.filter(

        notesheet=note

    ).filter(

        Q(visible_to=user) |
        Q(visible_to__isnull=True)

    ).order_by('created_at')

    return {

        'note': note,

        'remarks': remarks,
            'user': user,

        'can_edit': note.can_user_edit(user),

        'current_holder': note.forwarded_to,

        'procurement_actions': get_procurement_actions(
            note,
            user
        ),

        'users': User.objects.filter(
            is_deleted=False,
            status=True
        ).exclude(id=user.id)
    }


def inbox(request):
    user = get_session_user(request)
    if not user:
        return redirect('login')

    notes = (
        NoteSheet.objects.filter(forwarded_to=user)
        .select_related('department', 'created_by', 'forwarded_to')
        .prefetch_related('remarks')
        .order_by('-created_at')
    )
    return render(request, 'services/inbox.html', {'notes': notes, 'current_user': user})


def note_action(request, pk):
    user = get_session_user(request)
    if not user:
        return redirect('login')

    note = get_note_for_user(user, pk)
    if not note.can_user_edit(user):
        messages.error(request, "Only the officer currently holding the file can take action on it.")
        return redirect('open_sent_file', pk=note.id)

    users = User.objects.filter(is_deleted=False, status=True).exclude(id=user.id).order_by('officer_name')
    if request.method == "POST":
        action = request.POST.get('action')
        remark = request.POST.get('remark', '').strip()
        forwarded_to_id = request.POST.get('forwarded_to')
        forwarded_to = User.objects.filter(id=forwarded_to_id, is_deleted=False, status=True).first() if forwarded_to_id else None

        if action == 'FORWARDED':
            if not forwarded_to:
                messages.error(request, "Please select an officer to forward the file.")
                return redirect('note_action', pk=note.id)
            note.forwarded_to = forwarded_to
            note.save(update_fields=['forwarded_to'])
        elif action == 'REVERT':
            note.forwarded_to = forwarded_to or note.created_by
            note.save(update_fields=['forwarded_to'])

        add_workflow_remark(note, user, action, text=remark, forwarded_to=forwarded_to if action == 'FORWARDED' else note.forwarded_to)
        messages.success(request, "Action captured successfully.")
        return redirect('sent_notes')

    return render(request, 'services/action.html', {'note': note, 'users': users})


def sent_notes(request):
    user = get_session_user(request)
    if not user:
        return redirect('login')

    sent_items = (
        NoteRemark.objects.filter(created_by=user)
        .select_related('notesheet', 'notesheet__department', 'forwarded_to')
        .order_by('-created_at')
    )
    return render(request, 'services/sent_notes.html', {'sent_items': sent_items})


def detail_note(request, pk):
    user = get_session_user(request)
    if not user:
        return redirect('login')

    note = get_note_for_user(user, pk)
    return render(request, 'services/detail_note.html', build_note_context( note, user))


def build_notesheet_summary(note):
    first_forward = note.remarks.filter(action='FORWARDED').select_related('created_by', 'forwarded_to').order_by('created_at').first()
    latest_remark = note.remarks.select_related('created_by', 'forwarded_to').order_by('-created_at').first()

    return {
        'note': note,
        'sent_on_at': first_forward.created_at if first_forward else note.created_at,
        'sent_on_by': first_forward.created_by if first_forward else note.created_by,
        'sent_on_to': first_forward.forwarded_to if first_forward else note.forwarded_to,
        'current_status_at': latest_remark.created_at if latest_remark else note.created_at,
        'current_status_by': latest_remark.created_by if latest_remark else note.created_by,
        'current_holder': note.current_holder(),
        'status_label': PROCUREMENT_STATUS_LABELS.get(note.procurement_status, note.procurement_status),
    }




def open_sent_file(request, pk):
    user = get_session_user(request)
    if not user:
        return redirect('login')

    note = get_note_for_user(user, pk)
    return render(request, 'services/note_file.html', build_note_context(note, user))


def notesheet_search(request):
    user = get_session_user(request)
    if not user:
        return redirect('login')

    query = request.GET.get('q', '').strip()
    result = None

    if query:
        note = (
            NoteSheet.objects.filter(notesheet_no__icontains=query)
            .select_related('department', 'created_by', 'forwarded_to')
            .prefetch_related('remarks__created_by', 'remarks__forwarded_to')
            .order_by('-created_at')
            .first()
        )
        if note:
            result = build_notesheet_summary(note)
        else:
            messages.warning(request, "No notesheet found for that number.")

    return render(request, 'services/notesheet_search.html', {
        'query': query,
        'result': result,
    })















#movement history.
def movement_history(request, pk):

    user = get_user(request)

    if not user:

        return redirect('login')

    note = get_object_or_404(
        NoteSheet,
        id=pk
    )

    movements = NoteRemark.objects.filter(

        notesheet=note,

        action__in=[
            'FORWARDED',
            'APPROVED',
            'REVERT',
            'REJECTED'
        ]

    ).select_related(

        'created_by',
        'forwarded_to'

    ).order_by('created_at')

    context = {

        'note': note,

        'movements': movements

    }

    return render(

        request,

        'services/movement_history.html',

        context
    )










def chairman_purchase_approve(request, pk):

    user = get_user(request)

    note = get_object_or_404(
        NoteSheet,
        id=pk
    )

    if not is_chairman_user(user):

        messages.error(
            request,
            "Only chairman can approve."
        )

        return redirect(
            'edit_notesheet',
            pk=pk
        )

    if note.procurement_status != 'PURCHASE_PENDING_CHAIRMAN':

        messages.error(
            request,
            "Invalid workflow stage."
        )

        return redirect(
            'edit_notesheet',
            pk=pk
        )

    note.forwarded_to = note.created_by

    note.procurement_status = 'QUOTATION_ENTRY'

    note.save(
        update_fields=[
            'forwarded_to',
            'procurement_status'
        ]
    )

    NoteRemark.objects.create(

        notesheet=note,

        action='APPROVED',

        created_by=user,

        forwarded_to=note.created_by,

        remark_text='Purchase request approved by Chairman.'
    )

    messages.success(
        request,
        "Purchase approved."
    )

    return redirect(
        'edit_notesheet',
        pk=pk
    )


# =====================================================
# ADD QUOTATION
# =====================================================

def add_quotation(request, pk):

    user = get_user(request)

    note = get_object_or_404(
        NoteSheet,
        id=pk
    )

    if request.method != "POST":

        return redirect(
            'edit_notesheet',
            pk=pk
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
        'quotation_file')

    QuotationItem.objects.create(

        notesheet=note,

        item_name=item_name,

        quantity=quantity,

        unit_price=unit_price
    )

    chairman = get_chairman_user()

    note.forwarded_to = chairman

    note.procurement_status = (
        'QUOTATION_PENDING_CHAIRMAN'
    )

    note.save()

    NoteRemark.objects.create(

        notesheet=note,

        action='FORWARDED',

        created_by=user,

        forwarded_to=chairman,

        remark_text='Quotation uploaded.'
    )

    messages.success(
        request,
        "Quotation uploaded."
    )

    return redirect(
        'edit_notesheet',
        pk=pk
    )


# =====================================================
# CHAIRMAN QUOTATION APPROVE
# =====================================================

def chairman_quotation_approve(request, pk):

    user = get_user(request)

    note = get_object_or_404(
        NoteSheet,
        id=pk
    )

    note.forwarded_to = note.created_by

    note.procurement_status = (
        'VENDOR_SELECTION'
    )

    note.save()

    NoteRemark.objects.create(

        notesheet=note,

        action='APPROVED',

        created_by=user,

        forwarded_to=note.created_by,

        remark_text='Quotation approved.'
    )

    messages.success(
        request,
        "Quotation approved."
    )

    return redirect(
        'edit_notesheet',
        pk=pk
    )


# =====================================================
# ADD VENDOR
# =====================================================

def add_vendor(request, pk):

    user = get_user(request)

    note = get_object_or_404(
        NoteSheet,
        id=pk
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

        # address=request.POST.get(
        #     'address'
        # )
    )

    chairman = get_chairman_user()

    note.forwarded_to = chairman

    note.procurement_status = (
        'FINAL_PENDING_CHAIRMAN'
    )

    note.save()

    NoteRemark.objects.create(

        notesheet=note,

        action='FORWARDED',

        created_by=user,

        forwarded_to=chairman,

        remark_text='Vendor finalized.'
    )

    messages.success(
        request,
        "Vendor details saved."
    )

    return redirect(
        'edit_notesheet',
        pk=pk
    )


# =====================================================
# FINAL APPROVE
# =====================================================

def chairman_final_approve(request, pk):

    user = get_user(request)

    note = get_object_or_404(
        NoteSheet,
        id=pk
    )

    finance_user = get_finance_user()

    note.forwarded_to = finance_user

    note.procurement_status = (
        'FINANCE_PENDING'
    )

    note.save()

    generate_po_pdf(note)

    NoteRemark.objects.create(

        notesheet=note,

        action='APPROVED',

        created_by=user,

        forwarded_to=finance_user,

        remark_text='Final approval completed.'
    )

    messages.success(
        request,
        "Final approval completed."
    )

    return redirect(
        'edit_notesheet',
        pk=pk
    )


# =====================================================
# FINANCE APPROVE
# =====================================================

def finance_payment_approve(request, pk):

    user = get_user(request)

    note = get_object_or_404(
        NoteSheet,
        id=pk
    )

    note.procurement_status = (
        'INVENTORY_ENTRY'
    )

    note.forwarded_to = note.created_by

    note.save()

    NoteRemark.objects.create(

        notesheet=note,

        action='APPROVED',

        created_by=user,

        forwarded_to=note.created_by,

        remark_text='Finance approved payment.'
    )

    messages.success(
        request,
        "Finance approved."
    )

    return redirect(
        'edit_notesheet',
        pk=pk
    )


# =====================================================
# CLOSE INVENTORY
# =====================================================

def close_inventory(request, pk):

    note = get_object_or_404(
        NoteSheet,
        id=pk
    )

    items = QuotationItem.objects.filter(
        notesheet=note
    )

    vendor = VendorDetail.objects.filter(
        notesheet=note
    ).first()

    for item in items:

        InventoryRegister.objects.create(

            notesheet=note,

            item_name=item.item_name,

            quantity=item.quantity,

            unit_price=item.unit_price,

            vendor_name=vendor.vendor_name,

            stock_entry_date=date.today()
        )

    note.procurement_status = 'CLOSED'

    note.forwarded_to = None

    note.save()

    messages.success(
        request,
        "Inventory closed."
    )

    return redirect(
        'edit_notesheet',
        pk=pk
    )



def get_procurement_actions(note, user):

    actions = []

    status = note.procurement_status

    # =========================================
    # CHAIRMAN PURCHASE APPROVAL
    # =========================================

    if (
        is_chairman_user(user)
        and status == 'PURCHASE_PENDING_CHAIRMAN'
    ):

        actions.append({

            'key': 'chairman_purchase_approve',

            'label': 'Approve Purchase Request',

            'class': 'btn-success'
        })

    # =========================================
    # CHAIRMAN QUOTATION APPROVAL
    # =========================================

    elif (
        is_chairman_user(user)
        and status == 'QUOTATION_PENDING_CHAIRMAN'
    ):

        actions.append({

            'key': 'chairman_quotation_approve',

            'label': 'Approve Quotation',

            'class': 'btn-primary'
        })

    # =========================================
    # FINAL APPROVAL
    # =========================================

    elif (
        is_chairman_user(user)
        and status == 'FINAL_PENDING_CHAIRMAN'
    ):

        actions.append({

            'key': 'chairman_final_approve',

            'label': 'Final Approve & Generate PO',

            'class': 'btn-dark'
        })

    # =========================================
    # FINANCE APPROVAL
    # =========================================

    elif (
        is_finance_user(user)
        and status == 'FINANCE_PENDING'
    ):

        actions.append({

            'key': 'finance_payment_approve',

            'label': 'Approve Payment',

            'class': 'btn-warning'
        })

    # =========================================
    # CLOSE INVENTORY
    # =========================================

    elif (
        is_creator_admin(user, note)
        and status == 'INVENTORY_ENTRY'
    ):

        actions.append({

            'key': 'close_inventory',

            'label': 'Close Inventory',

            'class': 'btn-danger'
        })

    return actions


def generate_po_pdf(note):

    buffer = io.BytesIO()

    p = canvas.Canvas(buffer)

    # =========================================
    # HEADER
    # =========================================

    p.setFont(
        "Helvetica-Bold",
        18
    )

    p.drawString(
        180,
        800,
        "PURCHASE ORDER"
    )

    # =========================================
    # BASIC DETAILS
    # =========================================

    p.setFont(
        "Helvetica",
        12
    )

    p.drawString(
        50,
        760,
        f"Notesheet No : {note.notesheet_no}"
    )

    p.drawString(
        50,
        740,
        f"Date : {date.today()}"
    )

    # =========================================
    # VENDOR DETAILS
    # =========================================

    vendor = VendorDetail.objects.filter(
        notesheet=note
    ).first()

    if vendor:

        p.drawString(
            50,
            700,
            f"Vendor : {vendor.vendor_name}"
        )

        p.drawString(
            50,
            680,
            f"GST No : {vendor.gst_number}"
        )

        # p.drawString(
        #     50,
        #     660,
        #     f"Address : {vendor.address}"
        # )

    # =========================================
    # TABLE HEADER
    # =========================================

    y = 600

    p.setFont(
        "Helvetica-Bold",
        11
    )

    p.drawString(50, y, "Item")
    p.drawString(250, y, "Qty")
    p.drawString(320, y, "Unit Price")
    p.drawString(450, y, "Total")

    y -= 20

    # =========================================
    # ITEMS
    # =========================================

    p.setFont(
        "Helvetica",
        11
    )

    grand_total = Decimal('0.00')

    items = QuotationItem.objects.filter(
        notesheet=note
    )

    for item in items:

        total = (
            Decimal(item.quantity) *
            Decimal(item.unit_price)
        )

        grand_total += total

        p.drawString(
            50,
            y,
            str(item.item_name)
        )

        p.drawString(
            250,
            y,
            str(item.quantity)
        )

        p.drawString(
            320,
            y,
            str(item.unit_price)
        )

        p.drawString(
            450,
            y,
            str(total)
        )

        y -= 20

    # =========================================
    # GRAND TOTAL
    # =========================================

    y -= 20

    p.setFont(
        "Helvetica-Bold",
        12
    )

    p.drawString(
        320,
        y,
        "Grand Total :"
    )

    p.drawString(
        450,
        y,
        str(grand_total)
    )

    # =========================================
    # FOOTER
    # =========================================

    y -= 80

    p.setFont(
        "Helvetica",
        11
    )

    p.drawString(
        50,
        y,
        "Approved By Chairman"
    )

    # =========================================
    # SAVE PDF
    # =========================================

    p.showPage()

    p.save()

    pdf = buffer.getvalue()

    buffer.close()

    filename = (
        f"PO_{note.notesheet_no}.pdf"
    )

    note.purchase_order_file.save(

        filename,

        ContentFile(pdf),

        save=True
    )