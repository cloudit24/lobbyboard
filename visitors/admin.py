from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Visit, VisitPurpose


@admin.register(VisitPurpose)
class VisitPurposeAdmin(admin.ModelAdmin):
    list_display = ("name", "order", "is_active")
    list_editable = ("order", "is_active")


@admin.register(Visit)
class VisitAdmin(SimpleHistoryAdmin):
    list_display = ("name", "company", "purpose", "meeting_with", "checked_in_at", "checked_out_at", "registered_by")
    list_filter = ("purpose", "registered_by", ("checked_out_at", admin.EmptyFieldListFilter))
    search_fields = ("name", "phone", "email", "company", "meeting_with", "badge", "id_number")
    date_hierarchy = "checked_in_at"
    readonly_fields = ("registered_by", "checked_out_by")
