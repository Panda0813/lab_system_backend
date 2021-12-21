from django.contrib import admin
from users.models import User


class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'telephone', 'employee_no', 'email', 'section']


admin.site.register(User, UserAdmin)
