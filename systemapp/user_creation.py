from django.shortcuts import render, redirect, get_object_or_404
from userapp.models import User, RoleMaster
from systemapp.models import Collage

def user_list(request):
    users = User.objects.filter(
        is_deleted=False
    ).select_related(
        'role',
        'collage'
    ).order_by('-id')

    return render(
        request,
        'services/user_list.html',
        {'users': users}
    )


def user_save(request, pk=None):

    user_obj = None

    if pk:
        user_obj = get_object_or_404(
            User,
            pk=pk,
            is_deleted=False
        )

    if request.method == "POST":

        login_id = request.POST.get('login_id')
        password = request.POST.get('password')
        role = request.POST.get('role')
        officer_name = request.POST.get('officer_name')
        collage = request.POST.get('collage')
        designation = request.POST.get('designation')
        mobile_no = request.POST.get('mobile_no')
        status = request.POST.get('status') == "on"

        if user_obj:

            user_obj.login_id = login_id
            user_obj.password = password
            user_obj.role_id = role
            user_obj.officer_name = officer_name
            user_obj.collage_id = collage
            user_obj.designation = designation
            user_obj.mobile_no = mobile_no or None
            user_obj.status = status

            user_obj.save()

        else:

            User.objects.create(
                login_id=login_id,
                password=password,
                role_id=role,
                officer_name=officer_name,
                collage_id=collage,
               
                designation=designation,
                mobile_no=mobile_no or None,
                status=status
            )

        return redirect('user_list')

    roles = RoleMaster.objects.filter(
        is_deleted=False,
        status=True
    )

    collages = Collage.objects.all()

    return render(
        request,
        'services/user_form.html',
        {
            'user_obj': user_obj,
            'roles': roles,
            'collages': collages
        }
    )


def user_delete(request, pk):

    user_obj = get_object_or_404(
        User,
        pk=pk
    )

    user_obj.is_deleted = True
    user_obj.save()

    return redirect('user_list')
