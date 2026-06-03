from django.shortcuts import redirect, render

from .models import User

def login_view(request):
    if request.method == 'POST':
        login_id = request.POST['login_id']
        password = request.POST['password']

        try:
            user = User.objects.get(login_id=login_id, password=password)

            request.session['user_id'] = user.id #store in session
            request.session['officer_name'] = user.officer_name
            request.session['role'] = user.role.role_name


            return redirect('dashboard')

        except User.DoesNotExist:
            return render(request, 'login.html', {'error': 'Invalid credentials'})

    return render(request, 'login.html')


def get_session_user(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return None
    return User.objects.filter(id=user_id, is_deleted=False, status=True).first()


def dashboard(request):

    user = get_session_user(request)

    if not user:
        return redirect('login')

    from systemapp.models import (
        Department,
        NoteRemark,
        NoteSheet
    )

    selected_department = request.GET.get(
        'department',
        ''
    ).strip()

    # ==========================================
    # ONLY INBOX NOTES
    # ==========================================

    notes_list = NoteSheet.objects.filter(
        forwarded_to=user
    ).select_related(
        'department',
        'created_by',
        'forwarded_to'
    ).distinct()

    # ==========================================
    # DEPARTMENT FILTER
    # ==========================================

    if selected_department:

        notes_list = notes_list.filter(
            department_id=selected_department
        )

    # ==========================================
    # ONLY EDITABLE NOTES
    # ==========================================

    dashboard_notes = []

    for note in notes_list.order_by('-created_at'):

        if note.can_user_edit(user):

            dashboard_notes.append({

                "instance": note,

                "current_holder": note.current_holder(),

                "can_edit": True,

            })

    # ==========================================
    # CONTEXT
    # ==========================================

    context = {

        "accessible_notes": notes_list.count(),

        "inbox_count": NoteSheet.objects.filter(
            forwarded_to=user
        ).count(),

        "draft_count": NoteSheet.objects.filter(
            created_by=user,
            forwarded_to__isnull=True
        ).count(),

        "sent_count": NoteRemark.objects.filter(
            created_by=user,
            action='FORWARDED'
        ).count(),

        "departments": Department.objects.filter(
            is_deleted=False
        ).order_by('department_name'),

        "selected_department": selected_department,

        "dashboard_notes": dashboard_notes,

    }

    return render(
        request,
        "dashboard.html",
        context
    )



def logout_view(request):
    request.session.flush()
    return redirect('login')
