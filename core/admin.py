from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from simple_history.admin import SimpleHistoryAdmin

from .models import DisplaySettings, NetworkSettings, NewsFeed, ThemeSettings, TickerMessage


@admin.register(DisplaySettings)
class DisplaySettingsAdmin(SimpleHistoryAdmin):
    """One settings page - the list view jumps straight to it."""

    fieldsets = [
        ("Top bar", {"description": "The name and logo at the top of every screen.",
                     "fields": ["org_name_ar", "org_name_en", "logo", "logo_initials",
                                ("logo_name_ar", "logo_name_en"), "logo_tag"]}),
        ("Welcome screen", {"description": "Shown in the middle when no video or photos are playing.",
                            "fields": ["welcome_ar", "welcome_en", "welcome_sub", "youtube_id"]}),
        ("Prayer times", {"fields": ["show_prayer", ("city", "country"), "prayer_method",
                                     "pause_music_for_prayer"]}),
        ("Sea and weather", {"description": "Live figures from Open-Meteo (free). The badge turns yellow or red "
                                            "when wind or waves pass these limits.",
                             "fields": ["show_marine", ("sea_latitude", "sea_longitude"),
                                        ("location_name_ar", "location_name_en"),
                                        ("caution_wind_kn", "danger_wind_kn"), ("caution_wave_m", "danger_wave_m"),
                                        "sea_note_ar", "sea_note_en"]}),
        ("Contact box", {"description": "Blank lines are hidden.",
                         "fields": ["phone", "mobile", "email", "website", "address", "qr_url", "qr_label"]}),
        ("News, photos and logs", {"fields": ["show_news", "ticker_label", "slide_seconds", "log_retention_days"]}),
    ]

    def get_object(self, request, object_id, from_field=None):
        return DisplaySettings.load()  # always the single row, created on first visit

    def changelist_view(self, request, extra_context=None):
        DisplaySettings.load()
        return redirect(reverse("admin:core_displaysettings_change", args=[1]))

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(NewsFeed)
class NewsFeedAdmin(SimpleHistoryAdmin):
    list_display = ("label", "url", "language", "order", "is_active")
    list_editable = ("order", "is_active")
    list_filter = ("language",)


@admin.register(TickerMessage)
class TickerMessageAdmin(SimpleHistoryAdmin):
    list_display = ("text", "order", "is_active", "starts_at", "ends_at")
    list_editable = ("order", "is_active")
    search_fields = ("text",)


class SingletonAdmin(SimpleHistoryAdmin):
    def get_object(self, request, object_id, from_field=None):
        return self.model.load()

    def changelist_view(self, request, extra_context=None):
        self.model.load()
        opts = self.model._meta
        return redirect(reverse(f"admin:{opts.app_label}_{opts.model_name}_change", args=[1]))

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ThemeSettings)
class ThemeSettingsAdmin(SingletonAdmin):
    fields = ["brand_name", ("primary", "primary_dark"), ("secondary", "background"), "font_family"]

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        from django import forms
        if db_field.name in ("primary", "primary_dark", "secondary", "background"):
            kwargs["widget"] = forms.TextInput(attrs={"type": "color"})
        return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(NetworkSettings)
class NetworkSettingsAdmin(SingletonAdmin):
    fields = ["port", "how_to_apply", "lan_addresses", "public_hostnames"]
    readonly_fields = ["how_to_apply"]

    @admin.display(description="Changing the port")
    def how_to_apply(self, obj):
        from django.utils.safestring import mark_safe
        return mark_safe(
            "The app can't move its own door while it's open: after saving a new port, run "
            "<code>scripts/apply-network.ps1</code> (Windows) or <code>scripts/apply-network.sh</code> "
            "on the server. Local and tunnel addresses below work straight away, no restart.")
