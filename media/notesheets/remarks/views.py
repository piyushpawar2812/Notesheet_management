from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib import messages

from .models import User
import hashlib
from userapp.models import User

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
    if not request.session.get('user_id'):
        return redirect('login')
    return render(request, "dashboard.html")



def logout_view(request):
    request.session.flush()
    return redirect('login')
