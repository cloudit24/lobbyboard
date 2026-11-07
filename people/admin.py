from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from simple_history.admin import SimpleHistoryAdmin

from .models import AgentProfile


class AgentProfileInline(admin.StackedInline):
    model = AgentProfile
    can_delete = False
    extra = 0
    fields = ("display_name", "job_title", "extension")


admin.site.unregister(User)


@admin.register(User)
class PersonAdmin(UserAdmin):
    """Django's user page plus the desk profile. Roles = groups:
    Admins (also tick Staff), Secretaries, Reception, Customer care."""
    inlines = [AgentProfileInline]
    list_display = ("username", "first_name", "last_name", "email", "roles", "is_active", "is_staff", "last_login")
    list_filter = ("groups", "is_active", "is_staff", "is_superuser")

    @admin.display(description="Roles")
    def roles(self, obj):
        return ", ".join(obj.groups.values_list("name", flat=True)) or ("Admin" if obj.is_superuser else "-")


@admin.register(AgentProfile)
class AgentProfileAdmin(SimpleHistoryAdmin):
    list_display = ("user", "display_name", "job_title", "extension")
    search_fields = ("user__username", "display_name", "user__first_name", "user__last_name")
