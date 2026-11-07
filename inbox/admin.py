from django import forms
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin

from . import mail
from .models import Attachment, Enquiry, MailSettings, Message, Queue


class MailSettingsForm(forms.ModelForm):
    class Meta:
        model = MailSettings
        fields = "__all__"
        widgets = {"imap_password": forms.PasswordInput(render_value=True),
                   "smtp_password": forms.PasswordInput(render_value=True)}


@admin.register(MailSettings)
class MailSettingsAdmin(SimpleHistoryAdmin):
    form = MailSettingsForm
    readonly_fields = ("status",)
    fieldsets = [
        (None, {"fields": ["status", "enabled"]}),
        ("Incoming - the mailbox enquiries arrive in", {"fields": [
            ("imap_host", "imap_port", "imap_ssl"), "imap_user", "imap_password", "imap_folder", "poll_seconds"]}),
        ("Outgoing - how replies are sent", {"fields": [
            ("smtp_host", "smtp_port", "smtp_security"), "smtp_user", "smtp_password",
            "from_email", "from_name_pattern", "signature", "cc_emails", "notify_agents"]}),
    ]

    @admin.display(description="Status")
    def status(self, obj):
        test_url = reverse("admin:inbox_mailsettings_test")
        last = obj.last_checked.strftime("%d %b %H:%M") if obj.last_checked else "never"
        err = format_html('<br><span class="fd-badge is-alert">{}</span>', obj.last_error) if obj.last_error else ""
        return format_html('Last checked: {}{}<br><a class="fd-btn" href="{}">Test the connection</a> '
                           '<small class="fd-muted">(save first)</small>', last, err, test_url)

    def get_urls(self):
        return [path("test/", self.admin_site.admin_view(self.test_view), name="inbox_mailsettings_test")] + super().get_urls()

    def test_view(self, request):
        ok, text = mail.test_connection()
        (messages.success if ok else messages.error)(request, text)
        return redirect(reverse("admin:inbox_mailsettings_change", args=[1]))

    def get_object(self, request, object_id, from_field=None):
        return MailSettings.load()

    def changelist_view(self, request, extra_context=None):
        MailSettings.load()
        return redirect(reverse("admin:inbox_mailsettings_change", args=[1]))

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Queue)
class QueueAdmin(SimpleHistoryAdmin):
    list_display = ("name", "agent_names", "auto_assign", "is_default", "order", "is_active")
    list_editable = ("order", "is_active")
    filter_horizontal = ("agents",)

    @admin.display(description="Agents")
    def agent_names(self, obj):
        return ", ".join(u.get_username() for u in obj.agents.all()) or "-"


class MessageInline(admin.StackedInline):
    model = Message
    extra = 0
    fields = ("kind", "from_email", "cc", "subject", "body", "sent_by", "created_at", "send_error")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Enquiry)
class EnquiryAdmin(SimpleHistoryAdmin):
    list_display = ("ref", "subject", "customer_name", "customer_email", "queue", "assigned_to", "status", "created_at")
    list_filter = ("status", "queue", "assigned_to", "source")
    search_fields = ("subject", "customer_name", "customer_email", "customer_phone", "messages__body")
    date_hierarchy = "created_at"
    inlines = [MessageInline]


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("filename", "message", "size")

    def has_add_permission(self, request):
        return False
