import json

from django.contrib import admin, messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin

from core.models import bump_content_version

from . import widgets
from .models import AboutObjective, AboutProduct, AboutUs, AboutValue, Occasion, Screen


@admin.register(Screen)
class ScreenAdmin(SimpleHistoryAdmin):
    list_display = ("name", "status", "now_playing", "tv_address", "control", "is_active")
    list_editable = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("agents",)
    readonly_fields = ("tv_address", "status", "now_playing", "last_ip")
    fields = ("name", "slug", "tv_address", "layout_link", "is_active", "agents", "notes", "status", "now_playing",
              "last_ip")
    readonly_fields = readonly_fields + ("layout_link",)

    @admin.display(description="Layout")
    def layout_link(self, obj):
        if not obj.pk:
            return "Save first."
        return format_html('<a class="fd-btn" href="{}">Design this TV</a>',
                           reverse("admin:screens_screen_layout", args=[obj.pk]))

    def get_urls(self):
        return [path("<int:pk>/layout/", self.admin_site.admin_view(self.layout_view),
                     name="screens_screen_layout")] + super().get_urls()

    def layout_view(self, request, pk):
        """Drag-and-drop designer: place, move and resize the widgets on one TV."""
        scr = get_object_or_404(Screen, pk=pk)
        if not self.has_change_permission(request, scr):
            return redirect("admin:index")
        if request.method == "POST":
            action = request.POST.get("action")
            if action == "reset":
                scr.layout = []
                msg = "Back to the standard layout."
            elif action == "copy":
                src = Screen.objects.filter(pk=request.POST.get("source")).first()
                scr.layout = list(src.layout) if src else scr.layout
                msg = f"Copied the layout of {src}." if src else "Pick a TV to copy from."
            else:
                try:
                    scr.layout = widgets.clean(json.loads(request.POST.get("layout") or "[]"))
                except ValueError:
                    messages.error(request, "The layout could not be read. Nothing was saved.")
                    return redirect(request.path)
                msg = "Layout saved. The TV reloads with it in a few seconds."
            scr.save(update_fields=["layout"])
            bump_content_version()   # the TV reloads itself on its next check
            messages.success(request, msg)
            return redirect(request.path)
        current = widgets.clean(scr.layout) if scr.layout else widgets.DEFAULT_LAYOUT
        return render(request, "admin/screens/layout.html", {
            **self.admin_site.each_context(request), "title": f"Design: {scr.name}", "screen": scr,
            "opts": self.model._meta, "original": scr,
            "layout": current, "cols": widgets.COLS, "rows": widgets.ROWS,
            "catalog": {k: {"label": v[0], "minW": v[1], "minH": v[2]} for k, v in widgets.WIDGETS.items()},
            "others": Screen.objects.exclude(pk=scr.pk),
        })

    @admin.display(description="Status")
    def status(self, obj):
        if not obj.pk:
            return "-"
        if obj.is_online:
            return format_html('<span class="fd-badge">● Online</span>')
        return format_html('<span class="fd-badge is-alert">Offline</span>')

    @admin.display(description="Address to open on the TV")
    def tv_address(self, obj):
        if not obj.pk:
            return "Save first."
        url = reverse("screen", args=[obj.slug])
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', url, url)

    @admin.display(description="")
    def control(self, obj):
        return format_html('<a class="fd-btn" href="{}">Control</a>', reverse("agent:screen", args=[obj.slug]))


@admin.register(Occasion)
class OccasionAdmin(SimpleHistoryAdmin):
    list_display = ("name", "running_now", "theme", "mode", "starts_at", "ends_at", "is_active")
    list_filter = ("is_active", "theme")
    filter_horizontal = ("screens",)
    fieldsets = [
        (None, {"fields": ["name", "is_active", ("greeting_ar", "greeting_en"), "theme"]}),
        ("What plays", {"fields": ["mode", "photos", "videos", "songs", "shuffle_songs", "video_every_minutes",
                                   "full_screen"],
                        "description": "Build the lists first under Library > Playlists, from approved files."}),
        ("When", {"fields": [("starts_at", "ends_at"), "is_on", "screens"],
                  "description": "Give dates and it starts and stops by itself. Agents can also press "
                                 "Play now / Stop on their TV page. Prayer pauses still apply."}),
    ]

    @admin.display(boolean=True, description="Running now")
    def running_now(self, obj):
        return obj.running()


class AboutValueInline(admin.TabularInline):
    model = AboutValue
    extra = 0


class AboutObjectiveInline(admin.StackedInline):
    model = AboutObjective
    extra = 0


class AboutProductInline(admin.StackedInline):
    model = AboutProduct
    extra = 0
    fields = ("name_ar", "name_en", "icon_preview", "icon_svg", "show", "order")
    readonly_fields = ("icon_preview",)

    @admin.display(description="Icon")
    def icon_preview(self, obj):
        url = obj.icon_url() if obj and obj.pk else ""
        return format_html('<img src="{}" width="40" height="40" style="background:#0b1220;border-radius:8px;padding:6px">', url) if url else "-"


@admin.register(AboutUs)
class AboutUsAdmin(SimpleHistoryAdmin):
    fields = ("is_on", "vision_ar", "vision_en", "mission_ar", "mission_en", "products_url")
    inlines = [AboutValueInline, AboutObjectiveInline, AboutProductInline]

    def has_add_permission(self, request):
        return not AboutUs.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
