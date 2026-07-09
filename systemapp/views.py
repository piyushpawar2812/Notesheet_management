import io

from datetime import date

from decimal import Decimal
from urllib import request

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

from .models import Department, NoteRemark, NoteSheet,Purpose
from .models import *

PROCUREMENT_STATUS_LABELS = dict(NoteSheet.PROCUREMENT_STATUS_CHOICES)
GENERAL_STATUS_LABELS=dict(NoteSheet.GENERAL_STATUS_CHOICE)

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

def is_purchase_user(user):
    role_key = get_role_key(user)
    return "purchase" in role_key

def is_admin_user(user):
    role_key = get_role_key(user)
    return "admin" in role_key

def is_chairman_or_admin(user):
    """Check if user is chairman or admin"""
    role_key = get_role_key(user)
    return "chairman" in role_key or "admin" in role_key

def get_accessible_notes_queryset(user):
    role = user.role.role_name.lower()

    base_qs = (
        NoteSheet.objects
        .filter(is_deleted=False)
        .select_related(
            'department',
            'created_by',
            'forwarded_to',
            'purpose'
        )
        .prefetch_related('remarks')
    )

    if role in ['chairman', 'admin']:
        return base_qs.order_by('-created_at')

    return (
        base_qs.filter(
            Q(created_by=user) |
            Q(forwarded_to=user) |
            Q(remarks__created_by=user) |
            Q(remarks__forwarded_to=user)
        )
        .distinct()
        .order_by('-created_at')
    )


# def get_note_for_user(user, pk):
#     return get_object_or_404(get_accessible_notes_queryset(user), pk=pk)
def get_note_for_user(user, pk):

    role = user.role.role_name.lower()

    if role in ['admin', 'chairman']:
        return get_object_or_404(
            NoteSheet.objects.select_related(
                'department',
                'created_by',
                'forwarded_to'
            ),
            pk=pk
        )

    return get_object_or_404(
        get_accessible_notes_queryset(user),
        pk=pk
    )


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


def get_purchase_user():
    return find_workflow_user("purchase")

def get_admin_user():
    return find_workflow_user("admin")

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

    # Remove department, we don't need it anymore
    purpose = Purpose.objects.all().order_by('purpose_name')

    if request.method == "POST":
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        purpose_id = request.POST.get('purpose')

        if not title:
            messages.error(request, "Title is required.")
            return redirect('create_notesheet')

        # Get purpose
        purpose = Purpose.objects.filter(id=purpose_id).first() if purpose_id else None
        
        # Auto-assign collage from logged-in user
        collage = user.collage if user.collage else None
        
        # Create notesheet with collage from user
        note = NoteSheet.objects.create(
            title=title,
            description=description,
            collage=collage,  # Automatically from user
            purpose=purpose,
            created_by=user
        )

        messages.success(request, "Notesheet created successfully.")
        return redirect('edit_notesheet', pk=note.id)



    return render(request, 'services/create_notesheet.html', {'purpose': purpose})

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
    return render(request, 'services/your_notesheets.html', {'notes': notes, 'current_user': user,})

def delete_notesheet(request, pk):
    user = get_session_user(request)
    if not user:
        return redirect("login")

    note = get_object_or_404(NoteSheet, pk=pk, is_deleted=False)

    # only creator can delete
    if note.created_by_id != user.id:
        messages.error(request, "You are not authorized to delete this notesheet.")
        return redirect("your_notesheets")

    # if already forwarded, don't allow delete
    if note.forwarded_to_id is not None:
        messages.error(request, "This notesheet has already been forwarded and cannot be deleted.")
        return redirect("your_notesheets")

    note.is_deleted = True
    note.save(update_fields=["is_deleted"])

    messages.success(request, "Notesheet deleted successfully.")
    return redirect("your_notesheets")

    # =====================================
    # SOFT DELETE
    # =====================================
    note.is_deleted = True
    note.save(update_fields=["is_deleted"])

    messages.success(
        request,
        "Notesheet deleted successfully."
    )
    return redirect("your_notesheets")

# =========================================================
# OPEN NOTESHEET
# =========================================================

def edit_notesheet(request, pk):

    user = get_user(request)

    if not user:

        return redirect('login')

    note = get_note_for_user(
        user,
        pk
    )

    # =====================================
    # POST ACTIONS
    # =====================================

    if request.method == "POST":

        return handle_post(
            request,
            note,
            user
        )

    # =====================================
    # PAGE CONTEXT
    # =====================================

    context = build_note_context(
        note,
        user
    )

    # =====================================
    # RENDER
    # =====================================

    return render(
        request,
        'services/note_file.html',
        context
    )



def inbox(request):
    user = get_session_user(request)

    if not user:
        return redirect('login')

    notes = (
        NoteSheet.objects.filter(forwarded_to=user)
        .select_related(
            'department',
            'created_by',
            'forwarded_to',
            'purpose'
        )
        .prefetch_related(
            'remarks'
        )
        .order_by('-created_at')
    )

    for note in notes:
        note.can_edit = note.can_user_edit(user)

    return render(
        request,
        'services/inbox.html',
        {
            'notes': notes,
            'current_user': user
        }
    )

def handle_post(request, note, user):
    print("========== HANDLE_POST ==========")
    print(request.method)
    print(request.POST)

    # =====================================
    # WORKFLOW CLOSED CHECK
    # =====================================

    if note.procurement_status == "CLOSED":

        messages.error(
            request,
            "Workflow closed."
        )

        return redirect(
            'edit_notesheet',
            pk=note.id
        )

    action_type = request.POST.get("action_type")

# =====================================
# SAVE
# =====================================

    if action_type == "save":

        saved=save_note_content(
            request,
            note,
            user
        )
        print("SAVE RESULT =", saved)

        if not saved:
            print("SAVE FAILED")
            return redirect("edit_notesheet", pk=note.id)

        print("CALLING FORWARD")

        return redirect(
            "edit_notesheet",
            pk=note.id
        )
    
    elif action_type == "send":

        saved = save_note_content(
            request,
            note,
            user
        )

        if not saved:
            return redirect("edit_notesheet", pk=note.id)

        return forward_note(
            request,
            note,
            user
        )
    


    # # =====================================
    # # SEND
    # # =====================================

    # elif action_type == "send":

    #     # TinyMCE data
    #     text = request.POST.get("content", "").strip()
    #     attachment = request.FILES.get("remark_attachment")
    #     general_status = request.POST.get("general_status")

    #     print("======== DEBUG ========")
    #     print("Text:", repr(text))
    #     print("Attachment:", attachment)
    #     print("General Status:", repr(general_status))
    #     print("=======================")

    #     # ---------------------------------
    #     # Purchase Validation
    #     # ---------------------------------
    #     if (
    #         note.purpose
    #         and note.purpose.purpose_name
    #         and note.purpose.purpose_name.lower() == "purchase"
    #     ):

    #         if not text and not attachment:
    #             messages.error(
    #                 request,
    #                 "Please write a remark or attach a document before forwarding."
    #             )
    #             return redirect("edit_notesheet", pk=note.id)

    #     # ---------------------------------
    #     # Normal Validation
    #     # ---------------------------------
    #     else:

    #         if not text and not attachment and not general_status:
    #             messages.error(
    #                 request,
    #                 "Please write a remark, attach a document or select a status before forwarding."
    #             )
    #             return redirect("edit_notesheet", pk=note.id)

    #     # ---------------------------------
    #     # Save Current Remark
    #     # ---------------------------------
    #     saved = save_note_content(
    #         request,
    #         note,
    #         user
    #     )

    #     if not saved:
    #         return redirect(
    #             "edit_notesheet",
    #             pk=note.id
    #         )

    #     # ---------------------------------
    #     # Forward File
    #     # ---------------------------------
    #     return forward_note(
    #         request,
    #         note,
    #         user
    #     )

    # =====================================
    # CHAIRMAN / ADMIN COMMON ACCESS
    # =====================================

    chairman_access_actions = [
        'chairman_purchase_approve',
        'chairman_quotation_approve',
        'chairman_quotation_revert',
        'chairman_billing_approve',
    ]

    if action_type in chairman_access_actions:

        if request.session.get('role', '').lower() not in ['chairman', 'admin']:

            messages.error(
                request,
                "You are not authorized for this action."
            )

            return redirect(
                'edit_notesheet',
                pk=note.id
            )

    # =====================================
    # CHAIRMAN PURCHASE APPROVE
    # =====================================

    if action_type == 'chairman_purchase_approve':

        return chairman_purchase_approve(
            request,
            note.id
        )

    # =====================================
    # CHAIRMAN QUOTATION APPROVE
    # =====================================

    # elif action_type == 'chairman_quotation_approve':

    #     return chairman_quotation_approve(
    #         request,
    #         note.id
    #     )

    # # =====================================
    # # CHAIRMAN QUOTATION REVERT
    # # =====================================

    # elif action_type == 'chairman_quotation_revert':

    #     return chairman_quotation_revert(
    #         request,
    #         note.id
    #     )

    # =====================================
    # GENERATE PO
    # =====================================

    elif action_type == 'generate_po':

        return generate_po(
            request,
            note.id
        )

    # =====================================
    # INVENTORY ENTRY
    # =====================================

    elif action_type == 'inventory_received':

        return inventory_received(
            request,
            note.id
        )
    

    
    elif action_type == 'chairman_billing_approve':

        return chairman_billing_approve(
            request,
            note.id
        )
    

    elif action_type == 'finance_final_approve':

        return finance_final_approve(
            request,
            note.id
        )
    # =========================================
    # FINANCE SEND TO CHAIRMAN
    # =========================================

    # elif action_type == 'finance_send_to_chairman':

    #     return finance_send_to_chairman(
    #         request,
    #         note.id
    #     )

    # =========================================
    # CHAIRMAN BILLING APPROVE
    # =========================================

    # elif action_type == 'chairman_billing_approve':

    #     return chairman_billing_approve(
    #         request,
    #         note.id
    #     )

    # # =========================================
    # # FINANCE FINAL APPROVE
    # # =========================================

    # elif action_type == 'finance_final_approve':

    #     return finance_final_approve(
    #         request,
    #         note.id
    #     )



    return redirect(
        'edit_notesheet',
        pk=note.id
    )
    # =========================================
    # WORKFLOW CLOSED CHECK
    # =========================================

   
    # =========================================
    # INVALID ACTION
    # =========================================


# =========================================================
# SAVE NOTE CONTENT
# =========================================================
def save_note_content(request, note, user):
    print("===== save_note_content CALLED =====")

    text = request.POST.get('content', '').strip()
    attachment = request.FILES.get('remark_attachment')
    general_status = request.POST.get('general_status')

    # Check if this is the first remark
    first_remark = not NoteRemark.objects.filter(notesheet=note).exists()

    # Validation only for first row
    if first_remark and not text and not attachment and not general_status:
        messages.error(
            request,
            "The first remark must contain either text, an attachment, or a status."
        )
        return False

    # =====================================
    # Default action
    # =====================================

    action = "COMMENT"

    # =====================================
    # GENERAL APPROVAL (Except Purchase)
    # =====================================

    if (
        note.purpose
        and note.purpose.purpose_name.lower() != "purchase"
    ):

        role = user.role.role_name.lower()

        if role in ["chairman", "admin", "director"]:

            if general_status in ["APPROVED", "REJECTED"]:

                note.general_status = general_status

                if general_status == "APPROVED":
                    note.approved_by = user
                    action = "APPROVED"
                else:
                    note.approved_by = None
                    action = "REJECTED"

                note.save(
                    update_fields=[
                        "general_status",
                        "approved_by",
                    ]
                )

    # =====================================
    # SAVE REMARK
    # =====================================
    print("Creating NoteRemark...")
    NoteRemark.objects.create(
        notesheet=note,
        created_by=user,
        action=action,
        remark_text=text,
        attachment=attachment,
        visible_to=user,
        general_status=general_status if general_status else None,
        approved_by = user if general_status in ("APPROVED", "REJECTED") else None
    )

    messages.success(
        request,
        "Note saved successfully."
    )

    return True
# =========================================================
# FORWARD FILE
# =========================================================
def forward_note(request, note, user):
    print("1st step-----------------------")

    forwarded_to_id = request.POST.get("forwarded_to")

    # =====================================
    # VALIDATION
    # =====================================

    if not forwarded_to_id:
        messages.error(request, "Select officer before forwarding.")
        return redirect("edit_notesheet", pk=note.id)

    forwarded_user = User.objects.filter(
        id=forwarded_to_id,
        is_deleted=False,
        status=True
    ).first()

    if not forwarded_user:
        messages.error(request, "Invalid officer selected.")
        return redirect("edit_notesheet", pk=note.id)

    if forwarded_user.id == user.id:
        messages.error(request, "Cannot forward to yourself.")
        return redirect("edit_notesheet", pk=note.id)

    # =====================================
    # PURCHASE WORKFLOW
    # =====================================

    role_name = ""

    if forwarded_user.role and forwarded_user.role.role_name:
        role_name = forwarded_user.role.role_name.strip().lower()

    if (
        note.purpose
        and note.purpose.purpose_name
        and note.purpose.purpose_name.lower() == "purchase"
    ):

        if role_name in ["chairman", "admin"]:
            note.procurement_status = "PURCHASE_PENDING_CHAIRMAN"

    # =====================================
    # CURRENT USER SNAPSHOT
    # =====================================

    current_remarks = (
        NoteRemark.objects.filter(
            notesheet=note,
            visible_to=user
        )
        .order_by("created_at")
    )
    print("Forwarded User:", forwarded_user)
    print("2ndddd Current Remarks Count:", current_remarks.count())

    # =====================================
    # UPDATE LAST REMARK'S FORWARDED TO
    # =====================================

    last_remark = current_remarks.last()

    if last_remark:
        last_remark.forwarded_to = forwarded_user
        last_remark.save(update_fields=["forwarded_to"])

    # =====================================
    # REMOVE OLD SNAPSHOT OF NEXT USER
    # =====================================

    NoteRemark.objects.filter(
        notesheet=note,
        visible_to=forwarded_user
    ).delete()

    # =====================================
    # COPY COMPLETE HISTORY
    # =====================================
    print("3st step-----------------------")
    for old in current_remarks:
        print("4th step-----------------------")

        new_remark = NoteRemark.objects.create(
            notesheet=note,
            created_by=old.created_by,
            action=old.action,
            remark_text=old.remark_text,
            attachment=old.attachment,
            forwarded_to=old.forwarded_to,
            visible_to=forwarded_user,
            general_status=old.general_status,
            approved_by=old.approved_by,
        )
        print("5th step-----------------------")

        new_remark.created_at = old.created_at
        new_remark.save(update_fields=["created_at"])

        print("Remarks Count:9999999999999", current_remarks.count())

    # =====================================
    # MOVE FILE
    # =====================================

    note.forwarded_to = forwarded_user

    note.save(
        update_fields=[
            "forwarded_to",
            "procurement_status",
        ]
    )

    messages.success(
        request,
        f"Notesheet forwarded to {forwarded_user.officer_name}."
    )
    
    
    return redirect(
        "edit_notesheet",
        pk=note.id
    )


def build_note_context(note, user):

    remarks = NoteRemark.objects.filter(

        notesheet=note

    ).filter(

        Q(visible_to=user) |
        Q(visible_to__isnull=True)

    ).order_by('created_at')

    quotations = VendorQuotationItem.objects.filter(
            quotation__notesheet=note

    )

    purchase_order = PurchaseOrder.objects.filter(
        notesheet=note
    ).first()

    return {

        'note': note,

        'remarks': remarks,

        'user': user,

        'quotations': quotations,

        'purchase_order': purchase_order,

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
        'general_label': GENERAL_STATUS_LABELS.get(note.general_status, note.general_status),
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


# PURCHASE_FLOW STARTING
def chairman_purchase_approve(request, pk):

    user = get_user(request)

    note = get_object_or_404(
        NoteSheet,
        id=pk
    )

    role = request.session.get(
        'role',
        ''
    ).lower()

    # =====================================
    # ROLE CHECK
    # =====================================

    if role not in ['chairman', 'admin']:

        messages.error(
            request,
            "Only chairman/admin can approve."
        )

        return redirect(
            'edit_notesheet',
            pk=pk
        )

    # =====================================
    # STATUS CHECK
    # =====================================

    if note.procurement_status != 'PURCHASE_PENDING_CHAIRMAN':

        messages.error(
            request,
            "Invalid workflow stage."
        )

        return redirect(
            'edit_notesheet',
            pk=pk
        )

    # =====================================
    # GET PURCHASE OFFICER
    # =====================================

    purchase_user = get_purchase_user()

    print("PURCHASE USER =", purchase_user.id)

    # =====================================
    # UPDATE NOTE
    # =====================================

    note.forwarded_to = purchase_user

    note.procurement_status = 'QUOTATION_ENTRY'

    note.save()

    # =====================================
    # REMARK ENTRY
    # =====================================

    NoteRemark.objects.create(

        notesheet=note,

        created_by=user,

        forwarded_to=purchase_user,

        visible_to=purchase_user,

        action='APPROVED',

        remark_text='Approved by Chairman/Admin.'
    )

    messages.success(
        request,
        "Purchase approved successfully."
    )

    return redirect(
        'edit_notesheet',
        pk=pk
    )


def quotation_details(request, pk):

    user = get_user(request)

    note = get_object_or_404(
        NoteSheet,
        id=pk
    )

    quotations = VendorQuotationItem.objects.filter(
            quotation__notesheet=note

    )

    return render(
        request,
        'services/quotation_details.html',
        {
            'note': note,
            'quotations': quotations
        }
    )
    
    
# def add_quotation(request, pk):

#     user = get_user(request)

#     note = get_object_or_404(
#         NoteSheet,
#         id=pk
#     )

#     if request.method != "POST":

#         return redirect(
#             'edit_notesheet',
#             pk=pk
#         )

#     QuotationItem.objects.create(

#         notesheet=note,

#         vendor_name=request.POST.get(
#             'vendor_name'
#         ),

#         gst_number=request.POST.get(
#             'gst_number'
#         ),

#         item_name=request.POST.get(
#             'item_name'
#         ),

#         quantity=request.POST.get(
#             'quantity'
#         ),

#         unit_price=request.POST.get(
#             'unit_price'
#         ),

#         quote_price=request.POST.get(
#             'quote_price'
#         ),

#         address=request.POST.get(
#             'address'
#         ),

#         quotation_file=request.FILES.get(
#             'quotation_file'
#         )
#     )
    
#     all_quotes = QuotationItem.objects.filter(
#     notesheet=note
# )

#     all_quotes.update(is_l1=False)

#     lowest = all_quotes.order_by('quote_price').first()

#     if lowest:

#         lowest.is_l1 = True

#         lowest.save(update_fields=['is_l1'])

#     NoteRemark.objects.create(

#         notesheet=note,

#         action='COMMENT',

#         created_by=user,
        

#         forwarded_to=user,

#         remark_text='Vendor quotation added.'
#     )
    

#     messages.success(
#         request,
#         "Quotation added successfully."
#     )

#     return redirect(
#         'edit_notesheet',
#         pk=pk
#     )


from decimal import Decimal

from django.contrib import messages

from django.shortcuts import (
    get_object_or_404,
    redirect
)

from .models import (
    NoteSheet,
    VendorQuotation,
    VendorQuotationItem,
    NoteRemark
)


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

    # =========================================
    # CREATE VENDOR
    # =========================================

    vendor = VendorQuotation.objects.create(

        notesheet=note,

        vendor_name=request.POST.get(
            'vendor_name'
        ),

        gst_number=request.POST.get(
            'gst_number'
        ),

        address=request.POST.get(
            'address'
        ),

        quotation_file=request.FILES.get(
            'quotation_file'
        )

    )

    # =========================================
    # ITEMS
    # =========================================

    item_names = request.POST.getlist(
        'item_name[]'
    )

    quantities = request.POST.getlist(
        'quantity[]'
    )

    unit_prices = request.POST.getlist(
        'unit_price[]'
    )

    quotation_prices = request.POST.getlist(
        'quotation_price[]'
    )

    total_amount = Decimal('0.00')

    for i in range(len(item_names)):

        item_total = (
            Decimal(quantities[i])
            * Decimal(quotation_prices[i])
        )

        VendorQuotationItem.objects.create(

            quotation=vendor,

            item_name=item_names[i],

            quantity=quantities[i],

            unit_price=unit_prices[i],

            quotation_price=quotation_prices[i],

            total_price=item_total

        )

        total_amount += item_total

    # =========================================
    # UPDATE TOTAL
    # =========================================

    vendor.total_amount = total_amount

    vendor.save()

    # =========================================
    # REMARK
    # =========================================

    NoteRemark.objects.create(

        notesheet=note,

        action='COMMENT',

        created_by=user,

        forwarded_to=user,

        remark_text='Vendor quotation added.'

    )

    messages.success(
        request,
        'Vendor quotation added successfully.'
    )

    return redirect(
        'edit_notesheet',
        pk=pk
    )


# =============================================
# SELECT WINNER
# =============================================

def select_vendor_winner(request, vendor_id):

    vendor = get_object_or_404(
        VendorQuotation,
        id=vendor_id
    )

    VendorQuotation.objects.filter(
        notesheet=vendor.notesheet
    ).update(is_winner=False)

    vendor.is_winner = True

    vendor.save()

    messages.success(
        request,
        'Winner selected successfully.'
    )

    return redirect(
        'edit_notesheet',
        pk=vendor.notesheet.id
    )




# # =====================================================
# # CHAIRMAN QUOTATION APPROVE
# # =====================================================
# def send_quotation_to_chairman(request, pk):
    
#     user = get_user(request)
    
#     note = get_object_or_404(
#         NoteSheet,
#         id=pk
#     )
    
#     # =============================================
#     # VALIDATION 1: Check if any vendor quotation exists
#     # =============================================
#     vendor_exists = VendorQuotation.objects.filter(
#         notesheet=note
#     ).exists()
    
#     if not vendor_exists:
#         messages.error(
#             request,
#             "No vendor quotations found. Please add at least one vendor quotation before sending to Chairman."
#         )
#         return redirect(
#             'edit_notesheet',
#             pk=pk
#         )
    
#     # =============================================
#     # VALIDATION 2: Check if winner is selected
#     # =============================================
#     winner_exists = VendorQuotation.objects.filter(
#         notesheet=note,
#         is_winner=True
#     ).exists()
    
#     if not winner_exists:
#         messages.error(
#             request,
#             "Please select a winner vendor before sending quotation to Chairman."
#         )
#         return redirect(
#             'edit_notesheet',
#             pk=pk
#         )
    
#     # =============================================
#     # VALIDATION 3: Get winner and check data
#     # =============================================
#     winner = VendorQuotation.objects.get(
#         notesheet=note,
#         is_winner=True
#     )
    
#     # ✅ FIX: Check only vendor_name, NOT quotation_file
#     if not winner.vendor_name:
#         messages.error(
#             request,
#             "Winner vendor name is missing. Please ensure all details are filled."
#         )
#         return redirect(
#             'edit_notesheet',
#             pk=pk
#         )
    
#     # =============================================
#     # VALIDATION 4: Check if winner has items
#     # =============================================
#     winner_has_items = VendorQuotationItem.objects.filter(
#         quotation=winner
#     ).exists()
    
#     if not winner_has_items:
#         messages.error(
#             request,
#             "Winner quotation has no items. Please add items before sending to Chairman."
#         )
#         return redirect(
#             'edit_notesheet',
#             pk=pk
#         )
    
#     # =============================================
#     # PROCEED WITH SENDING TO CHAIRMAN
#     # =============================================
#     chairman = get_chairman_user()
    
#     note.forwarded_to = chairman
#     note.procurement_status = 'QUOTATION_PENDING_CHAIRMAN'
#     note.save()
    
#     NoteRemark.objects.create(
#         notesheet=note,
#         action='FORWARDED',
#         created_by=user,
#         forwarded_to=chairman,
#         remark_text='Quotation submitted to chairman.'
#     )
    
#     messages.success(
#         request,
#         "Quotation sent to Chairman successfully."
#     )
    
#     return redirect(
#         'edit_notesheet',
#         pk=pk
#     )




# def chairman_quotation_approve(request, pk):

#     user = get_user(request)

#     note = get_object_or_404(NoteSheet, id=pk)

#     purchase_user = get_purchase_user()

#     note.forwarded_to = purchase_user

#     note.procurement_status = 'PO_PENDING'

#     note.save()

#     messages.success(
#         request,
#         "Quotation approved."
#     )

#     return redirect(
#         'edit_notesheet',
#         pk=pk
#     )
    
    
# def chairman_quotation_revert(request, pk):

#     user = get_user(request)

#     note = get_object_or_404(
#         NoteSheet,
#         id=pk
#     )

#     purchase_user = get_purchase_user()

#     note.forwarded_to = purchase_user

#     note.procurement_status = (
#         'QUOTATION_REVERT'
#     )

#     note.save()

#     NoteRemark.objects.create(

#         notesheet=note,

#         action='REVERT',

#         created_by=user,

#         forwarded_to=purchase_user,

#         remark_text='Quotation reverted by chairman.'
#     )

#     messages.warning(
#         request,
#         "Quotation reverted."
#     )

#     return redirect(
#         'edit_notesheet',
#         pk=pk
#     )

from django.core.files.base import ContentFile

from reportlab.pdfgen import canvas
def generate_po(request, pk):

    user = get_user(request)

    note = get_object_or_404(
        NoteSheet,
        id=pk
    )

    # ====================================
    # GET WINNER VENDOR
    # ====================================

    vendor = VendorQuotation.objects.filter(

        notesheet=note,

        is_winner=True

    ).prefetch_related(
        'items'
    ).first()

    if not vendor:

        messages.error(
            request,
            "No winner vendor selected."
        )

        return redirect(
            'edit_notesheet',
            pk=pk
        )

    # ====================================
    # PURCHASE USER
    # ====================================

    purchase_user = get_purchase_user()

    # ====================================
    # PO NUMBER
    # ====================================

    po_number = (
        f"PO-{uuid.uuid4().hex[:8].upper()}"
    )

    # ====================================
    # PDF BUFFER
    # ====================================

    buffer = io.BytesIO()

    p = canvas.Canvas(buffer)

    # ====================================
    # TITLE
    # ====================================

    p.setFont(
        "Helvetica-Bold",
        18
    )

    p.drawString(
        200,
        800,
        "PURCHASE ORDER"
    )

    # ====================================
    # NOTESHEET DETAILS
    # ====================================

    p.setFont(
        "Helvetica",
        12
    )

    p.drawString(
        50,
        760,
        f"PO Number : {po_number}"
    )

    p.drawString(
        50,
        735,
        f"Notesheet No : {note.notesheet_no}"
    )

    p.drawString(
        50,
        710,
        f"Vendor Name : {vendor.vendor_name}"
    )

    p.drawString(
        50,
        685,
        f"GST Number : {vendor.gst_number}"
    )

    p.drawString(
        50,
        660,
        f"Address : {vendor.address}"
    )

    # ====================================
    # TABLE HEADER
    # ====================================

    y = 610

    p.setFont(
        "Helvetica-Bold",
        11
    )

    p.drawString(50, y, "Item")
    p.drawString(220, y, "Qty")
    p.drawString(300, y, "Unit Price")
    p.drawString(420, y, "Total")

    y -= 20

    # ====================================
    # ITEMS
    # ====================================

    p.setFont(
        "Helvetica",
        10
    )

    grand_total = 0

    for item in vendor.items.all():

        p.drawString(
            50,
            y,
            str(item.item_name)
        )

        p.drawString(
            220,
            y,
            str(item.quantity)
        )

        p.drawString(
            300,
            y,
            str(item.quotation_price)
        )

        p.drawString(
            420,
            y,
            str(item.total_price)
        )

        grand_total += item.total_price

        y -= 20

    # ====================================
    # GRAND TOTAL
    # ====================================

    y -= 20

    p.setFont(
        "Helvetica-Bold",
        12
    )

    p.drawString(
        300,
        y,
        f"Grand Total : ₹ {grand_total}"
    )

    # ====================================
    # FOOTER
    # ====================================

    y -= 60

    p.setFont(
        "Helvetica",
        10
    )

    p.drawString(
        50,
        y,
        "Authorized Signature"
    )

    # ====================================
    # SAVE PDF
    # ====================================

    p.save()

    pdf = buffer.getvalue()

    buffer.close()

    # ====================================
    # SAVE PDF FILE
    # ====================================

    note.po_pdf.save(

        f"{po_number}.pdf",

        ContentFile(pdf),

        save=False

    )

    # ====================================
    # UPDATE NOTE
    # ====================================

    note.purchase_order_no = po_number

    note.procurement_status = (
        'INVENTORY_PENDING'
    )

    note.forwarded_to = purchase_user

    note.save()

    # ====================================
    # REMARK
    # ====================================

    NoteRemark.objects.create(

        notesheet=note,

        created_by=user,

        forwarded_to=purchase_user,

        action='PO_GENERATED',

        remark_text=(
            f"Purchase Order Generated : "
            f"{po_number}"
        ),

        visible_to=purchase_user

    )

    # ====================================
    # SUCCESS MESSAGE
    # ====================================

    messages.success(

        request,

        "Purchase Order Generated Successfully."

    )

    return redirect(

        'edit_notesheet',

        pk=pk

    )
 
def inventory_received(request, pk):
    """Purchase Officer receives inventory and sends to Chairman/Admin for billing approval"""
    
    user = get_user(request)
    note = get_object_or_404(NoteSheet, id=pk)
    
    # ==========================================
    # GET WINNER VENDOR
    # ==========================================
    vendor = VendorQuotation.objects.filter(
        notesheet=note,
        is_winner=True
    ).prefetch_related('items').first()
    
    if not vendor:
        messages.error(request, "Winner vendor not found.")
        return redirect('edit_notesheet', pk=pk)
    
    # ==========================================
    # SAVE INVENTORY ITEMS
    # ==========================================
    for item in vendor.items.all():
        received_qty = request.POST.get(f'quantity_{item.id}') or item.quantity
        
        InventoryItem.objects.create(
            notesheet=note,
            item_name=item.item_name,
            quantity=received_qty,
            price=item.quotation_price,
            supplier_name=vendor.vendor_name,
            added_date=request.POST.get('added_date'),
            description=request.POST.get('remark_text', ''),
            is_available=True if int(received_qty) > 0 else False
        )
    
    # ==========================================
    # GET CHAIRMAN/ADMIN USER
    # ==========================================
    chairman_user = get_chairman_user()
    
    # ==========================================
    # UPDATE NOTE - Send to Chairman/Admin for billing approval
    # ==========================================
    note.procurement_status = 'BILL_PENDING_CHAIRMAN'  # ✅ Chairman/Admin ko bhej rahe hain
    note.forwarded_to = chairman_user
    note.save()
    
    # ==========================================
    # SAVE REMARK
    # ==========================================
    user_remark = request.POST.get('remark_text', 'Inventory received. Sent for billing approval.')
    
    NoteRemark.objects.create(
        notesheet=note,
        action='FORWARDED',
        created_by=user,
        forwarded_to=chairman_user,
        remark_text=user_remark,
        visible_to=chairman_user
    )
    
    messages.success(request, "✅ Inventory saved and sent to Chairman/Admin for billing approval.")
    return redirect('edit_notesheet', pk=pk)


# ==========================================
# 2. CHAIRMAN/ADMIN BILLING APPROVE
# ==========================================

def chairman_billing_approve(request, pk):
    """Chairman/Admin approves billing and sends to Finance for final closure"""
    
    user = get_user(request)
    note = get_object_or_404(NoteSheet, id=pk)
    
    # =====================================
    # ROLE CHECK - Chairman or Admin only
    # =====================================
    if not is_chairman_or_admin(user):
        messages.error(request, "Only Chairman or Admin can approve billing.")
        return redirect('edit_notesheet', pk=pk)
    
    # =====================================
    # GET FINANCE USER
    # =====================================
    finance_user = get_finance_user()
    
    # =====================================
    # UPDATE NOTE - Send to Finance for final closure
    # =====================================
    note.procurement_status = 'FINAL_FINANCE_APPROVAL'
    note.forwarded_to = finance_user
    note.save()
    
    # =====================================
    # USER REMARK
    # =====================================
    user_remark = request.POST.get('remark_text', 'Billing approved by Chairman/Admin.')
    
    # =====================================
    # SAVE REMARK
    # =====================================
    NoteRemark.objects.create(
        notesheet=note,
        action='APPROVED',
        created_by=user,
        forwarded_to=finance_user,
        remark_text=user_remark,
        visible_to=finance_user
    )
    
    messages.success(request, "✅ Billing approved. Sent to Finance for final closure.")
    return redirect('edit_notesheet', pk=pk)


# ==========================================
# 3. FINANCE FINAL APPROVE (CLOSE WORKFLOW)
# ==========================================
def finance_final_approve(request, pk):
    """Finance final approval and workflow closure"""
    
    user = get_user(request)
    note = get_object_or_404(NoteSheet, id=pk)
    
    # =====================================
    # ROLE CHECK - Finance only
    # =====================================
    role_key = get_role_key(user)
    if "finance" not in role_key:
        messages.error(request, "Only Finance can close the workflow.")
        return redirect('edit_notesheet', pk=pk)
    
    # =====================================
    # HANDLE ATTACHMENT (if any)
    # =====================================
    attachment = request.FILES.get('finance_attachment')
    if attachment:
        note.finance_attachment = attachment
        note.save()
    
    # =====================================
    # UPDATE NOTE - CLOSE WORKFLOW
    # =====================================
    note.procurement_status = 'CLOSED'
    note.is_closed = True
    note.forwarded_to = None
    note.save()
    
    # =====================================
    # SAVE REMARK WITH ATTACHMENT
    # =====================================
    user_remark = request.POST.get('remark_text', 'Workflow closed by Finance.')
    
    NoteRemark.objects.create(
        notesheet=note,
        action='APPROVED',
        created_by=user,
        forwarded_to=None,
        remark_text=user_remark,
        # attachment=attachment,  # ✅ Attachment added to remark
        visible_to=None
    )
    
    messages.success(request, "✅ Workflow closed successfully.")
    return redirect('edit_notesheet', pk=pk)


def get_procurement_actions(note, user):

    actions = []

    status = note.procurement_status

    # Chairman Purchase Approval
    if (
        is_chairman_user(user)
        and status == 'PURCHASE_PENDING_CHAIRMAN'
    ):

        actions.append({

            'key': 'chairman_purchase_approve',

            'label': 'Approve Purchase Request',

            'class': 'btn-success'
        })

    # # Chairman Quotation Approval
    # elif (
    #     is_chairman_user(user)
    #     and status == 'QUOTATION_PENDING_CHAIRMAN'
    # ):

    #     actions.append({

    #         'key': 'chairman_quotation_approve',

    #         'label': 'Approve Quotations',

    #         'class': 'btn-primary'
    #     })

    # Purchase Officer Generate PO
    elif (
        is_purchase_user(user)
        and status == 'PO_PENDING'
    ):

        actions.append({

            'key': 'generate_po',

            'label': 'Generate PO PDF',

            'class': 'btn-dark'
        })

    # Inventory Entry
    elif (
        is_purchase_user(user)
        and status == 'PO_GENERATED'
    ):

        actions.append({

            'key': 'inventory_received',

            'label': 'Register In Inventory',

            'class': 'btn-warning'
        })
    elif (is_purchase_user(user)
    and status == 'INVENTORY_PENDING'):
        actions.append({

        'key': 'inventory_received',

        'label': 'Material Received / Inventory Entry',

        'class': 'btn-success'
    })

    # # Finance Review
    # elif (
    #     is_finance_user(user)
    #     and status == 'FINANCE_REVIEW'
    # ):

    #     actions.append({

    #         'key': 'finance_send_to_chairman',

    #         'label': 'Send Bill To Chairman',

    #         'class': 'btn-info'
    #     })

    # Chairman Bill Approval
    elif (
        is_chairman_user(user)
        and status == 'BILL_PENDING_CHAIRMAN'
    ):

        actions.append({

            'key': 'chairman_billing_approve',

            'label': 'Approve Billing',

            'class': 'btn-success'
        })

    # Final Finance Approval
    elif (
        is_finance_user(user)
        and status == 'FINAL_FINANCE_APPROVAL'
    ):

        actions.append({

            'key': 'finance_final_approve',

            'label': 'Final Finance Approval',

            'class': 'btn-danger'
        })

    return actions





from django.shortcuts import render
from django.db.models import Count, Sum
from .models import NoteSheet


# =========================================
# DASHBOARD
# =========================================
def dashboard_view(request):
    user = get_session_user(request)
    if not user:
        return redirect('login')
    
    # =========================================
    # TOTALS
    # =========================================
    total_notesheets = NoteSheet.objects.count()
    total_purchase_notesheets = NoteSheet.objects.filter(
        purpose__purpose_name__iexact='purchase'
    ).count()
    total_closed_purchase = NoteSheet.objects.filter(
        procurement_status='CLOSED'
    ).count()
    total_spend = VendorQuotationItem.objects.filter(
        quotation__notesheet__procurement_status='CLOSED',
        quotation__is_winner=True
    ).aggregate(total=Sum('quotation_price'))['total'] or 0
    
    # =========================================
    # ALL NOTESHEETS
    # =========================================
    all_notesheets = (
    NoteSheet.objects
    .filter(is_deleted=False)
    .select_related(
        'department', 'created_by', 'forwarded_to', 'purpose', 'approved_by'
    )
    .prefetch_related('remarks')
    .order_by('-created_at')
)
    
    # =========================================
    # CREATE NOTEOPEN LIST WITH PERMISSIONS
    # =========================================
    noteopen = []
    for note in all_notesheets:
        noteopen.append({
            'instance': note,
            'can_edit': note.current_holder() == user, # ✅ Yahan add kiya
            'current_holder': note.current_holder(),
        })
    
    context = {
        'total_notesheets': total_notesheets,
        'total_purchase_notesheets': total_purchase_notesheets,
        'total_closed_purchase': total_closed_purchase,
        'total_spend': total_spend,
        'noteopen': noteopen,  # ✅ Template yehi use kar raha hai
        'current_user': user,
    }
    
    return render(request, 'services/dashboard_view.html', context)
