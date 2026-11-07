"""Logins, logouts and every add / change / delete of the project's data,
with old and new values. Who did it comes from the current request
(simple_history's middleware keeps it)."""
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import log_event

TRACKED_APPS = {"core", "library", "screens"}
TRACKED_MODELS = {"auth.User", "auth.Group"}
# Changed constantly by the screens themselves or already logged as agent actions.
UNTRACKED_MODELS = {"screens.ScreenState"}
UNTRACKED_FIELDS = {"id", "password", "last_login", "last_seen", "last_ip", "now_playing", "updated_at", "version"}


def _label(instance):
    return f"{instance._meta.app_label}.{instance._meta.object_name}"


def _tracked(instance):
    label = _label(instance)
    if label in UNTRACKED_MODELS or label.startswith(("audit.", "sessions.")) or ".Historical" in label:
        return False
    return instance._meta.app_label in TRACKED_APPS or label in TRACKED_MODELS


def _request():
    from simple_history.models import HistoricalRecords
    return getattr(HistoricalRecords.context, "request", None)


@receiver(user_logged_in)
def on_login_ok(sender, request, user, **kwargs):
    log_event("login_ok", f"{user.username} logged in", request=request, user=user)


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    if user:
        log_event("logout", f"{user.username} logged out", request=request, user=user)


@receiver(user_login_failed)
def on_login_fail(sender, credentials, request=None, **kwargs):
    name = credentials.get("username", "")[:150]
    log_event("login_fail", f"Failed login for “{name}”", request=request, user=name)


@receiver(pre_save)
def stash_old_values(sender, instance, **kwargs):
    if not _tracked(instance) or not instance.pk:
        return
    try:
        instance._audit_old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        instance._audit_old = None


@receiver(post_save)
def log_save(sender, instance, created, raw=False, **kwargs):
    if raw or not _tracked(instance):
        return
    old = getattr(instance, "_audit_old", None)
    changes = {}
    for field in instance._meta.fields:
        if field.name in UNTRACKED_FIELDS:
            continue
        new_val = getattr(instance, field.attname, None)
        old_val = getattr(old, field.attname, None) if old else None
        if str(old_val) != str(new_val):
            changes[field.name] = {"old": str(old_val)[:300], "new": str(new_val)[:300]}
    if not changes and not created:
        return
    what = f"{instance._meta.verbose_name.capitalize()} “{str(instance)[:120]}”"
    summary = f"Added {what}" if created else f"Changed {what}: " + ", ".join(changes)[:150]
    log_event("admin_add" if created else "admin_edit", summary, request=_request(),
              path=f"{_label(instance)}#{instance.pk}", changes=changes)


@receiver(post_delete)
def log_delete(sender, instance, **kwargs):
    if not _tracked(instance):
        return
    log_event("admin_delete", f"Deleted {instance._meta.verbose_name} “{str(instance)[:120]}”",
              request=_request(), path=f"{_label(instance)}#{instance.pk}")
