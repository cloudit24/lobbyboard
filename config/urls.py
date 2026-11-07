from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from core.dashboard import dashboard_context
from core.views import home

admin.site.site_header = f"{settings.APP_NAME} Admin"
admin.site.site_title = f"{settings.APP_NAME} Admin"
admin.site.index_title = "Control room"
admin.site.enable_nav_sidebar = False

# Must run before admin.site.urls is read below: Django binds the index view
# at that moment, so an override placed later is silently ignored.
_admin_index = admin.site.index


def _dashboard_index(request, extra_context=None):
    context = dashboard_context(request, admin.site.get_app_list(request))
    return _admin_index(request, {**context, **(extra_context or {})})


admin.site.index = _dashboard_index

urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(template_name="desk/login.html",
                                                 extra_context={"title": "Log in"}), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("agent/", include("desk.urls")),
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
