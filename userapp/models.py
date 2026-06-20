
from django.db import models
from systemapp.models import Collage

class RoleMaster(models.Model):
    role_name = models.CharField(max_length=100)

    status = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.role_name


class User(models.Model):
    login_id = models.CharField(max_length=100)
    password = models.CharField(max_length=100)
    role = models.ForeignKey(RoleMaster, on_delete=models.CASCADE)
    
    officer_name = models.CharField(max_length=100,blank=True)
    department=models.CharField(max_length=100,blank=True)
#NEW_added
    collage = models.ForeignKey('systemapp.Collage', on_delete=models.CASCADE,blank=True,null=True)

    employee_no = models.BigIntegerField(null=True, blank=True)
    designation = models.CharField(max_length=100,blank=True)
    mobile_no = models.BigIntegerField(null=True, blank=True) 

    status = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.login_id
