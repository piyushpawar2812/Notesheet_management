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

from .models import Department, NoteRemark, NoteSheet,Purpose
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

def is_purchase_user(user):
    role_key = get_role_key(user)
    return "purhase" in role_key


def get_accessible_notes_queryset(user):
    return (
        NoteSheet.objects.filter(
            Q(created_by=user)
            | Q(forwarded_to=user)
            | Q(remarks__created_by=user)
            | Q(remarks__forwarded_to=user)
        )
        .select_related('department', 'created_by', 'forwarded_to')
        .prefetch_related( 'remarks__created_by', 'remarks__forwarded_to', )
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


def get_purchase_user():
    return find_workflow_user("purchase")


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

def handle_post(request, note, user):

    action_type = request.POST.get(
        'action_type'
    )

    # =====================================
    # SAVE NOTE
    # =====================================

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

    # =====================================
    # FORWARD FILE
    # =====================================

    elif action_type == 'send':

        return forward_note(
            request,
            note,
            user
        )

    # =====================================
    # CHAIRMAN PURCHASE APPROVE
    # =====================================

    elif action_type == 'chairman_purchase_approve':

        return chairman_purchase_approve(
            request,
            note.id
        )

    # =====================================
    # CHAIRMAN QUOTATION APPROVE
    # =====================================

    elif action_type == 'chairman_quotation_approve':

        return chairman_quotation_approve(
            request,
            note.id
        )

    # =====================================
    # CHAIRMAN QUOTATION REVERT
    # =====================================

    elif action_type == 'chairman_quotation_revert':

        return chairman_quotation_revert(
            request,
            note.id
        )

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
        
    # =========================================
# FINANCE SEND TO CHAIRMAN
# =========================================

    elif action_type == 'finance_send_to_chairman':

        return finance_send_to_chairman(
        request,
        note.id
    )


# =========================================
# CHAIRMAN BILLING APPROVE
# =========================================

    elif action_type == 'chairman_billing_approve':

        return chairman_billing_approve(
        request,
        note.id
    )


# =========================================
# FINANCE FINAL APPROVE
# =========================================

    elif action_type == 'finance_final_approve':

        return finance_final_approve(
        request,
        note.id
    )

    return redirect(
    'edit_notesheet',
    pk=note.id
)
   
    # =========================================
    # INVALID ACTION
    # =========================================


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

        return False

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

    return True
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

        forwarded_to=forwarded_user,

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

    quotations = QuotationItem.objects.filter(
        notesheet=note
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

# PURCHASE_FLOW STARTING
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

    purchase_user = get_purchase_user()

    # =========================================
    # COPY FULL TRAIL TO PURCHASE OFFICER
    # =========================================

    current_remarks = NoteRemark.objects.filter(

        notesheet=note,

        visible_to=user

    ).order_by('created_at')

    # remove old snapshot

    NoteRemark.objects.filter(

        notesheet=note,

        visible_to=purchase_user

    ).delete()

    # recreate full trail

    for old in current_remarks:

        new_remark = NoteRemark.objects.create(

            notesheet=note,

            created_by=old.created_by,

            action=old.action,

            remark_text=old.remark_text,

            attachment=old.attachment,

            forwarded_to=purchase_user,

            visible_to=purchase_user
        )

        new_remark.created_at = old.created_at

        new_remark.save(
            update_fields=['created_at']
        )

    # =========================================
    # APPROVAL ENTRY
    # =========================================

    NoteRemark.objects.create(

        notesheet=note,

        action='APPROVED',

        created_by=user,

        forwarded_to=purchase_user,

        remark_text='Purchase request approved by Chairman.',

        visible_to=purchase_user
    )

    # =========================================
    # UPDATE NOTE
    # =========================================

    note.forwarded_to = purchase_user

    note.procurement_status = 'QUOTATION_ENTRY'

    note.save(
        update_fields=[
            'forwarded_to',
            'procurement_status'
        ]
    )

    messages.success(
        request,
        "Purchase approved."
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

    quotations = QuotationItem.objects.filter(
        notesheet=note
    )

    return render(
        request,
        'services/quotation_details.html',
        {
            'note': note,
            'quotations': quotations
        }
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

    QuotationItem.objects.create(

        notesheet=note,

        vendor_name=request.POST.get(
            'vendor_name'
        ),

        gst_number=request.POST.get(
            'gst_number'
        ),

        item_name=request.POST.get(
            'item_name'
        ),

        quantity=request.POST.get(
            'quantity'
        ),

        unit_price=request.POST.get(
            'unit_price'
        ),

        quote_price=request.POST.get(
            'quote_price'
        ),

        address=request.POST.get(
            'address'
        ),

        quotation_file=request.FILES.get(
            'quotation_file'
        )
    )
    
    all_quotes = QuotationItem.objects.filter(
    notesheet=note
)

    all_quotes.update(is_l1=False)

    lowest = all_quotes.order_by('quote_price').first()

    if lowest:

        lowest.is_l1 = True

        lowest.save(update_fields=['is_l1'])

    NoteRemark.objects.create(

        notesheet=note,

        action='COMMENT',

        created_by=user,
        

        forwarded_to=user,

        remark_text='Vendor quotation added.'
    )
    

    messages.success(
        request,
        "Quotation added successfully."
    )

    return redirect(
        'edit_notesheet',
        pk=pk
    )


# =====================================================
# CHAIRMAN QUOTATION APPROVE
# =====================================================
def send_quotation_to_chairman(request, pk):

    user = get_user(request)

    note = get_object_or_404(
        NoteSheet,
        id=pk
    )

    chairman = get_chairman_user()

    note.forwarded_to = chairman

    note.procurement_status = 'QUOTATION_PENDING_CHAIRMAN'

    note.save()

    NoteRemark.objects.create(

        notesheet=note,

        action='FORWARDED',

        created_by=user,

        forwarded_to=chairman,

        remark_text='Quotation submitted to chairman.'
    )

    messages.success(
        request,
        "Quotation sent."
    )

    return redirect(
        'edit_notesheet',
        pk=pk
    )

def chairman_quotation_approve(request, pk):

    user = get_user(request)

    note = get_object_or_404(NoteSheet, id=pk)

    purchase_user = get_purchase_user()

    note.forwarded_to = purchase_user

    note.procurement_status = 'PO_PENDING'

    note.save()

    messages.success(
        request,
        "Quotation approved."
    )

    return redirect(
        'edit_notesheet',
        pk=pk
    )
    
    
def chairman_quotation_revert(request, pk):

    user = get_user(request)

    note = get_object_or_404(
        NoteSheet,
        id=pk
    )

    purchase_user = get_purchase_user()

    note.forwarded_to = purchase_user

    note.procurement_status = (
        'QUOTATION_REVERT'
    )

    note.save()

    NoteRemark.objects.create(

        notesheet=note,

        action='REVERT',

        created_by=user,

        forwarded_to=purchase_user,

        remark_text='Quotation reverted by chairman.'
    )

    messages.warning(
        request,
        "Quotation reverted."
    )

    return redirect(
        'edit_notesheet',
        pk=pk
    )
def generate_po(request, pk):

    user = get_user(request)

    note = get_object_or_404(
        NoteSheet,
        id=pk
    )

    vendor = QuotationItem.objects.filter(

    notesheet=note,

    is_l1=True

    ).first()

    if not vendor:

        messages.error(
            request,
            "No vendor quotation found."
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
    # CREATE PDF
    # ====================================

    buffer = io.BytesIO()

    p = canvas.Canvas(buffer)

    p.setFont(
        "Helvetica-Bold",
        16
    )

    p.drawString(
        200,
        800,
        "PURCHASE ORDER"
    )
    
    p.setFont(
    "Helvetica",
    12
)
    p.drawString(
    100,
    770,
        f"Notesheet No: {note.notesheet_no}"
)

    p.setFont(
        "Helvetica",
        12
    )

    p.drawString(
        100,
        750,
        f"PO No: {po_number}"
    )

    p.drawString(
        100,
        720,
        f"Vendor: {vendor.vendor_name}"
    )

    p.drawString(
        100,
        690,
        f"Item: {vendor.item_name}"
    )

    p.drawString(
        100,
        660,
        f"Quantity: {vendor.quantity}"
    )

    p.drawString(
        100,
        630,
        f"Amount: {vendor.quote_price}"
    )

    p.save()

    pdf = buffer.getvalue()

    buffer.close()

    # ====================================
    # SAVE PDF
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
    # SAVE REMARK
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
    # SUCCESS
    # ====================================

    messages.success(
        request,
        "PO Generated Successfully."
    )

    return redirect(
        'edit_notesheet',
        pk=pk
    )
 
def inventory_received(request, pk):

    user = get_user(request)

    note = get_object_or_404(
        NoteSheet,
        id=pk
    )


    InventoryItem.objects.create(

        category=request.POST.get(
            'category'
        ),

        item_name=request.POST.get(
            'item_name'
        ),

        quantity=request.POST.get(
            'quantity'
        ),

        price=request.POST.get(
            'price'
        ) or 0,

        supplier_name=request.POST.get(
            'supplier_name'
        ),
        
        added_date=request.POST.get(
    'added_date'
),

        description=request.POST.get(
            'description'
        )
    )

    finance_user = get_finance_user()

    note.procurement_status = 'FINANCE_PENDING'

    note.forwarded_to = finance_user

    note.save()

    NoteRemark.objects.create(

        notesheet=note,

        action='APPROVED',

        created_by=user,

        forwarded_to=finance_user,

        remark_text='Inventory entry completed and sent to Finance.'
    )

    messages.success(
        request,
        "Inventory saved successfully."
    )

    return redirect(
        'edit_notesheet',
        pk=pk
    )       
    
def finance_send_to_chairman(request, pk):

    user = get_user(request)

    note = get_object_or_404(
        NoteSheet,
        id=pk
    )
    attachment = request.FILES.get(
        'finance_attachment'
    )

    chairman = get_chairman_user()

    # =====================================
    # COPY ALL REMARKS TO CHAIRMAN
    # =====================================

    current_remarks = NoteRemark.objects.filter(

        notesheet=note,

        visible_to=user

    ).order_by('created_at')

    # remove old copy

    NoteRemark.objects.filter(

        notesheet=note,

        visible_to=chairman

    ).delete()

    # recreate snapshot

    for old in current_remarks:

        new_remark = NoteRemark.objects.create(

            notesheet=note,

            created_by=old.created_by,

            action=old.action,

            remark_text=old.remark_text,

            attachment=old.attachment,

            forwarded_to=old.forwarded_to,

            visible_to=chairman
        )

        new_remark.created_at = old.created_at

        new_remark.save(
            update_fields=['created_at']
        )

    # =====================================
    # UPDATE NOTE
    # =====================================

    note.forwarded_to = chairman

    note.procurement_status = (
        'BILL_PENDING_CHAIRMAN'
    )

    note.save()

    # =====================================
    # WORKFLOW REMARK
    # =====================================

    NoteRemark.objects.create(

        notesheet=note,

        created_by=user,

        forwarded_to=chairman,

        action='FORWARDED',
        
        attachment=attachment,

        remark_text=(
            'Finance sent billing '
            'to Chairman for approval.'
        ),

        visible_to=chairman
    )

    messages.success(
        request,
        "Bill sent to chairman."
    )

    return redirect(
        'edit_notesheet',
        pk=pk
    )


def chairman_billing_approve(request, pk):

    user = get_user(request)

    note = get_object_or_404(
        NoteSheet,
        id=pk
    )

    # =====================================
    # ONLY CHAIRMAN
    # =====================================

    if not is_chairman_user(user):

        messages.error(
            request,
            "Only chairman can approve billing."
        )

        return redirect(
            'edit_notesheet',
            pk=pk
        )

    # =====================================
    # FINANCE USER
    # =====================================

    finance_user = get_finance_user()

    # =====================================
    # COPY FILE TO FINANCE
    # =====================================

    current_remarks = NoteRemark.objects.filter(

        notesheet=note,

        visible_to=user

    ).order_by('created_at')

    # remove old finance copy

    NoteRemark.objects.filter(

        notesheet=note,

        visible_to=finance_user

    ).delete()

    # recreate snapshot

    for old in current_remarks:

        new_remark = NoteRemark.objects.create(

            notesheet=note,

            created_by=old.created_by,

            action=old.action,

            remark_text=old.remark_text,

            attachment=old.attachment,

            forwarded_to=old.forwarded_to,

            visible_to=finance_user
        )

        new_remark.created_at = old.created_at

        new_remark.save(
            update_fields=['created_at']
        )

    # =====================================
    # UPDATE NOTE
    # =====================================

    note.forwarded_to = finance_user

    note.procurement_status = (
        'FINAL_FINANCE_APPROVAL'
    )

    note.save()

    # =====================================
    # WORKFLOW REMARK
    # =====================================

    NoteRemark.objects.create(

        notesheet=note,

        created_by=user,

        forwarded_to=finance_user,

        action='APPROVED',

        remark_text=(
            'Chairman approved billing.'
        ),

        visible_to=finance_user
    )

    messages.success(
        request,
        "Billing approved successfully."
    )

    return redirect(
        'edit_notesheet',
        pk=pk
    )


def finance_final_approve(request, pk):

    user = get_user(request)

    note = get_object_or_404(
        NoteSheet,
        id=pk
    )

    note.procurement_status = 'CLOSED'

    note.is_closed = True

    note.save()

    NoteRemark.objects.create(

        notesheet=note,

        action='APPROVED',

        created_by=user,

        remark_text='Workflow closed by Finance.'
    )

    messages.success(
        request,
        "Workflow closed successfully."
    )

    return redirect(
        'edit_notesheet',
        pk=pk
    )


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

    # Chairman Quotation Approval
    elif (
        is_chairman_user(user)
        and status == 'QUOTATION_PENDING_CHAIRMAN'
    ):

        actions.append({

            'key': 'chairman_quotation_approve',

            'label': 'Approve Quotations',

            'class': 'btn-primary'
        })

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

    # Finance Review
    elif (
        is_finance_user(user)
        and status == 'FINANCE_REVIEW'
    ):

        actions.append({

            'key': 'finance_send_to_chairman',

            'label': 'Send Bill To Chairman',

            'class': 'btn-info'
        })

    # Chairman Bill Approval
    elif (
        is_chairman_user(user)
        and status == 'BILL_PENDING_CHAIRMAN'
    ):

        actions.append({

            'key': 'chairman_bill_approve',

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
from .models import NoteSheet, QuotationItem


# =========================================
# DASHBOARD
# =========================================


def dashboard_view(request):

    # =========================================
    # TOTAL NOTESHEETS
    # =========================================

    total_notesheets = NoteSheet.objects.count()

    # =========================================
    # TOTAL PURCHASE NOTESHEETS
    # =========================================

    total_purchase_notesheets = (
        NoteSheet.objects.filter(
            purpose__purpose_name__iexact='purchase'
        ).count()
    )

    # =========================================
    # TOTAL CLOSED PURCHASE NOTESHEETS
    # =========================================

    total_closed_purchase = (
        NoteSheet.objects.filter(
            procurement_status='CLOSED'
        ).count()
    )

    # =========================================
    # TOTAL SPEND
    # ONLY CLOSED + L1 QUOTATIONS
    # =========================================

    total_spend = (
        QuotationItem.objects.filter(
            notesheet__procurement_status='CLOSED',
            is_l1=True
        ).aggregate(
            total=Sum('quote_price')
        )['total'] or 0
    )

    # =========================================
    # OFFICER WISE NOTESHEETS
    # =========================================

    officer_notesheets = (
        NoteSheet.objects.select_related(
            'created_by',
            'purpose'
        )
        .all()
        .order_by('-id')
    )

    context = {

        'total_notesheets': total_notesheets,

        'total_purchase_notesheets': total_purchase_notesheets,

        'total_closed_purchase': total_closed_purchase,

        'total_spend': total_spend,

        'officer_notesheets': officer_notesheets
    }

    return render(
        request,
        'services/dashboard_view.html',
        context
    )
