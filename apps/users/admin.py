from django.contrib import admin

from apps.users.models import User


@admin.register(User)
class UserModelAdmin(admin.ModelAdmin):
    list_display = ("id", "first_name", "last_name", "is_active", "is_system_admin")
    list_filter = ("is_active", "is_system_admin")
    search_fields = ("first_name", "last_name")
