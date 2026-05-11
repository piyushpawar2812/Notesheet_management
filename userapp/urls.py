from django.urls import path,include
from userapp.views import login_view, dashboard,logout_view
from . import views
urlpatterns = [
    path('', login_view, name='login'),
    path('dashboard/', dashboard, name='dashboard'),
    path('logout/', logout_view, name='logout'),
    
    
]
