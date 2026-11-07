import csv
import json

from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html

from .models import AuditLog


@admin.action(description="Export selected rows as CSV")
def export_as_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=logs.csv"
    writer = csv.writer(response)
    writer.writerow(["timestamp", "event", "user", "ip_address", "summary", "method", "path", "status_code",
                     "user_agent", "extra"])
    for row in queryset:
        writer.writerow([row.timestamp, row.event_type, row.user, row.ip_address, row.summary, row.method,
                         row.path, row.status_code, row.user_agent, row.extra])
    return response


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "event_type", "user", "what", "ip_address", "status_code")
    list_filter = ("event_type", "user", "status_code")
    search_fields = ("ip_address", "user", "path", "summary", "extra")
    date_hierarchy = "timestamp"
    actions = [export_as_csv]
    list_per_page = 50
    show_full_result_count = False  # big table: skip the slow "of N total" count
    readonly_fields = ("timestamp", "event_type", "user", "ip_address", "summary", "method", "path",
                       "status_code", "user_agent", "details")
    exclude = ("extra",)

    @admin.display(description="What")
    def what(self, obj):
        return obj.summary or f"{obj.method} {obj.path}"

    @admin.display(description="Details")
    def details(self, obj):
        if not obj.extra:
            return "-"
        try:
            pretty = json.dumps(json.loads(obj.extra), indent=2, ensure_ascii=False)
        except ValueError:
            pretty = obj.extra
        return format_html("<pre style='white-space:pre-wrap;margin:0'>{}</pre>", pretty)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
