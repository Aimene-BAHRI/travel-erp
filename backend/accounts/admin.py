from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Role, User


@admin.register(User)
class TravelUserAdmin(UserAdmin):
    ordering = ["email"]
    list_display = ["email", "agency", "branch", "is_active", "is_platform_admin"]
    fieldsets = UserAdmin.fieldsets + (
        ("Travel ERP", {"fields": ("agency", "branch", "roles", "is_platform_admin")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Travel ERP", {"fields": ("email", "agency", "branch", "is_platform_admin")}),
    )


admin.site.register(Role)
