from django.urls import path

from screens import views as tv

from . import views

app_name = "agent"
urlpatterns = [
    path("", views.home, name="home"),
    # Visitors registry
    path("visitors/", views.visitors, name="visitors"),
    path("visitors/<int:pk>/out/", views.visitor_out, name="visitor_out"),
    # Enquiries
    path("enquiries/", views.enquiries, name="enquiries"),
    path("enquiries/new/", views.enquiry_new, name="enquiry_new"),
    path("enquiries/<int:pk>/", views.enquiry, name="enquiry"),
    path("files/<int:pk>/", views.attachment, name="attachment"),
    # TVs and uploads
    path("tv/", tv.home, name="tv"),
    path("upload/", tv.upload, name="upload"),
    path("upload/<int:pk>/withdraw/", tv.delete_upload, name="delete_upload"),
    path("screen/<slug:slug>/", tv.screen, name="screen"),
    path("screen/<slug:slug>/status.json", tv.screen_status, name="screen_status"),
    # Secretary
    path("team/", views.team, name="team"),
    path("team/new/", views.team_edit, name="team_new"),
    path("team/<int:pk>/", views.team_edit, name="team_edit"),
    path("reports/", views.reports, name="reports"),
]
