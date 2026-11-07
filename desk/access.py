"""Who may open what in the desk dashboard. One place, so pages and menus agree."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from people.models import is_secretary


def can(user, area):
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    return {
        "tv": lambda: user.has_perm("screens.control_screen"),
        "upload": lambda: user.has_perm("library.upload_media"),
        "visitors": lambda: user.has_perm("visitors.register_visitor"),
        "enquiries": lambda: user.has_perm("inbox.handle_enquiries"),
        "secretary": lambda: is_secretary(user),
    }[area]()


def areas(user):
    return {a: can(user, a) for a in ("tv", "upload", "visitors", "enquiries", "secretary")}


def desk_user(user):
    return any(areas(user).values())


def needs(area=None):
    """Page decorator: logged in, and allowed into `area` (None = any desk area)."""
    def deco(view):
        @login_required
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            ok = can(request.user, area) if area else desk_user(request.user)
            if not ok:
                raise PermissionDenied("You don't have access to this page. Ask your secretary or an admin.")
            return view(request, *args, **kwargs)
        return wrapper
    return deco


def enquiry_scope(user):
    """Enquiries this person may see: secretaries all; agents their topics + assigned to them."""
    from django.db.models import Q

    from inbox.models import Enquiry
    qs = Enquiry.objects.select_related("queue", "assigned_to")
    if can(user, "secretary"):
        return qs
    return qs.filter(Q(assigned_to=user) | Q(queue__agents=user)).distinct()
