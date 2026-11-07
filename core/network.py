"""Which addresses may open the app.

The list is the ALLOWED_HOSTS from .env plus the local and tunnel addresses an
admin enters in Network settings - so adding a Cloudflare Tunnel name or a new
office IP needs no restart. Behind a tunnel the browser talks https to
Cloudflare; nginx passes that on (X-Forwarded-Proto) so logins and forms work.
"""
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponseBadRequest
from django.http.request import split_domain_port, validate_host

CACHE_KEY = "network:allowed_hosts"


def allowed_hosts():
    hosts = cache.get(CACHE_KEY)
    if hosts is None:
        from .models import NetworkSettings
        n = NetworkSettings.load()
        extra = [h for h in settings.ALLOWED_HOSTS if h != "*"]  # e.g. "testserver" during tests
        hosts = list(dict.fromkeys(settings.ENV_ALLOWED_HOSTS + extra + ["localhost", "127.0.0.1", "[::1]"]
                                   + n.lan_list() + n.public_list()))
        cache.set(CACHE_KEY, hosts, 60)
    return hosts


def forget():
    cache.delete(CACHE_KEY)


class AllowedHostsMiddleware:
    """Refuses requests for addresses that are not on the list."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if "*" not in settings.ENV_ALLOWED_HOSTS:
            domain, _port = split_domain_port(request.META.get("HTTP_HOST", "") or request.META.get("SERVER_NAME", ""))
            if not domain or not validate_host(domain, allowed_hosts()):
                return HttpResponseBadRequest(
                    "This address is not allowed. An admin can add it in Admin → Network settings.")
        return self.get_response(request)
