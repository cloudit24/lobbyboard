from django.db import transaction

from .models import AuditLog, client_ip

# Paths that would flood the log with no audit value: files, and the TV's own
# polling (every few seconds, per screen). Screens coming online are logged
# separately.
SKIP_PREFIXES = ("/static/", "/media/", "/healthz", "/api/", "/favicon.ico")


class AuditMiddleware:
    """One log row per page visit."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith(SKIP_PREFIXES):
            try:
                user = getattr(request, "user", None)
                with transaction.atomic():  # savepoint: a failed log row can't spoil anything else
                    AuditLog.objects.create(
                        ip_address=client_ip(request),
                        user=user.username if user and user.is_authenticated else "",
                        method=request.method or "",
                        path=request.path[:500],
                        status_code=response.status_code,
                        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
                    )
            except Exception:
                pass  # logging must never break the actual response
        return response
