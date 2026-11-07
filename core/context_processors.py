from django.conf import settings


def app_name(request):
    """App name for every page, plus the screens shown in the shortcuts bar."""
    ctx = {"APP_NAME": settings.APP_NAME}
    user = getattr(request, "user", None)
    if user and user.is_authenticated and (request.path.startswith(("/admin/", "/agent/"))):
        from screens.models import Screen
        if user.is_staff:
            ctx["fd_bar_screens"] = Screen.objects.filter(is_active=True)[:3]
        else:
            ctx["agent_screens"] = Screen.for_agent(user) if user.has_perm("screens.control_screen") else []
    return ctx


def desk(request):
    """Theme and menu for the desk dashboard pages (/agent/...)."""
    if not request.path.startswith(("/agent/", "/login/")):
        return {}
    from desk.access import areas
    from .models import DisplaySettings, ThemeSettings
    theme, display = ThemeSettings.load(), DisplaySettings.load()
    user = getattr(request, "user", None)
    return {
        "theme": theme,
        "brand": theme.brand_name or display.org_name_en or settings.APP_NAME,
        "brand_logo": display.logo.url if display.logo else "",
        "brand_initials": display.logo_initials,
        "can": areas(user) if user and user.is_authenticated else {},
    }
