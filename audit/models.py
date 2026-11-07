import json

from django.db import models, transaction


class AuditLog(models.Model):
    """One row per thing that happened. Written by the middleware (visits),
    signals (logins, edits, deletions) and log_event() (agent actions,
    uploads, reviews, screens coming back online). Read-only in the admin."""

    EVENT_CHOICES = [
        ("request", "Page visit"),
        ("login_ok", "Login"),
        ("login_fail", "Login failed"),
        ("logout", "Logout"),
        ("admin_add", "Added"),
        ("admin_edit", "Changed"),
        ("admin_delete", "Deleted"),
        ("agent_action", "Agent action"),
        ("upload", "Upload"),
        ("review", "Upload reviewed"),
        ("screen_online", "Screen online"),
        ("visitor", "Visitor"),
        ("enquiry", "Enquiry"),
        ("mail_error", "Mail problem"),
        ("desk", "Secretary action"),
    ]

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    user = models.CharField(max_length=150, blank=True, db_index=True)  # username, not FK: survives user deletion
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES, default="request", db_index=True)
    method = models.CharField(max_length=10, blank=True)
    path = models.CharField("Where / what", max_length=500, blank=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    summary = models.CharField(max_length=300, blank=True)
    extra = models.TextField(blank=True, help_text="JSON details, e.g. old and new values of an edit.")

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Log entry"
        verbose_name_plural = "Logs"

    def __str__(self):
        return f"[{self.get_event_type_display()}] {self.summary or self.path}"


def client_ip(request):
    if not request:
        return None
    return (request.META.get("HTTP_CF_CONNECTING_IP")
            or (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
            or request.META.get("REMOTE_ADDR")) or None


def log_event(event_type, summary="", request=None, user=None, path="", **details):
    """Write one log row. Never raises - logging must not break the action."""
    try:
        with transaction.atomic():  # a savepoint: a failed log row can't spoil the caller's transaction
            _write(event_type, summary, request, user, path, details)
    except Exception:
        pass


def _write(event_type, summary, request, user, path, details):
    if user is None and request is not None and getattr(request, "user", None) and request.user.is_authenticated:
        user = request.user
    AuditLog.objects.create(
        event_type=event_type,
        summary=summary[:300],
        user=(getattr(user, "username", None) or (user if isinstance(user, str) else "") or "")[:150],
        ip_address=client_ip(request),
        path=(path or (request.path if request else ""))[:500],
        method=(request.method or "") if request else "",
        extra=json.dumps(details, ensure_ascii=False, default=str)[:10000] if details else "",
    )
