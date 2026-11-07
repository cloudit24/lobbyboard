from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin

from audit.models import log_event

from .models import MediaItem, Playlist, PlaylistItem


def _review(request, queryset, status, verb):
    n = 0
    for item in queryset.exclude(status=status):
        item.status, item.reviewed_by, item.reviewed_at = status, request.user, timezone.now()
        item.save()
        log_event("review", f"{verb} “{item.title}” (uploaded by {item.uploaded_by or 'unknown'})",
                  request=request, path=f"library.MediaItem#{item.pk}")
        n += 1
    return n


@admin.action(description="Approve - agents can play them")
def approve(modeladmin, request, queryset):
    n = _review(request, queryset, "approved", "Approved")
    messages.success(request, f"{n} file(s) approved.")


@admin.action(description="Reject - hide them from agents")
def reject(modeladmin, request, queryset):
    n = _review(request, queryset, "rejected", "Rejected")
    messages.warning(request, f"{n} file(s) rejected. Add a note on each file to tell the agent why.")


@admin.register(MediaItem)
class MediaItemAdmin(SimpleHistoryAdmin):
    list_display = ("preview_small", "title", "kind", "status_badge", "order", "uploaded_by", "uploaded_at", "size_mb")
    list_display_links = ("preview_small", "title")
    list_editable = ("order",)
    list_filter = ("status", "kind", "uploaded_by")
    search_fields = ("title", "file")
    actions = [approve, reject]
    readonly_fields = ("preview", "kind", "size_mb", "uploaded_by", "uploaded_at", "reviewed_by", "reviewed_at")
    fields = ("preview", "title", "file", "status", "review_note", "order", "kind", "size_mb",
              "uploaded_by", "uploaded_at", "reviewed_by", "reviewed_at")
    list_per_page = 50

    @admin.display(description="")
    def preview_small(self, obj):
        if obj.kind == "image" and obj.file:
            return format_html('<img src="{}" style="width:64px;height:40px;object-fit:cover;border-radius:6px">', obj.file.url)
        return {"video": "🎬", "audio": "🎵"}.get(obj.kind, "📄")

    @admin.display(description="Preview")
    def preview(self, obj):
        if not obj or not obj.file:
            return "-"
        url = obj.file.url
        if obj.kind == "image":
            return format_html('<img src="{}" style="max-width:480px;max-height:270px;border-radius:10px">', url)
        if obj.kind == "video":
            return format_html('<video src="{}" controls preload="metadata" style="max-width:480px;border-radius:10px"></video>', url)
        return format_html('<audio src="{}" controls preload="metadata"></audio>', url)

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        alert = " is-alert" if obj.status == "pending" else ""
        return format_html('<span class="fd-badge{}">{}</span>', alert, obj.get_status_display())

    @admin.display(description="Size")
    def size_mb(self, obj):
        return f"{obj.size / 1048576:.1f} MB" if obj.size else "-"

    def save_model(self, request, obj, form, change):
        if not change:
            # Uploaded by an admin here: approved straight away.
            obj.uploaded_by = request.user
            if obj.status == "pending":
                obj.status = "approved"
        if "status" in form.changed_data and obj.status != "pending":
            obj.reviewed_by, obj.reviewed_at = request.user, timezone.now()
            log_event("review", f"{obj.get_status_display()} “{obj.title}”", request=request,
                      path=f"library.MediaItem#{obj.pk or 'new'}")
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        obj.file.delete(save=False)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.file.delete(save=False)
        super().delete_queryset(request, queryset)


class PlaylistItemInline(admin.TabularInline):
    model = PlaylistItem
    extra = 3
    autocomplete_fields = ("item",)
    fields = ("order", "item")
    ordering = ("order", "id")


@admin.register(Playlist)
class PlaylistAdmin(SimpleHistoryAdmin):
    list_display = ("name", "kind", "count", "order", "is_active")
    list_editable = ("order", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("name",)
    inlines = [PlaylistItemInline]

    @admin.display(description="Files")
    def count(self, obj):
        return obj.entries.count()
