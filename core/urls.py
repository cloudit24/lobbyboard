from django.urls import path

from . import views

urlpatterns = [
    path("screen/<slug:slug>/", views.screen, name="screen"),
    path("api/screens/<slug:slug>/state/", views.screen_state, name="screen_state"),
    path("api/about/", views.api_about, name="api_about"),
    path("api/weather/", views.api_weather, name="api_weather"),
    path("api/prayer/", views.api_prayer, name="api_prayer"),
    path("api/news/", views.api_news, name="api_news"),
    path("api/news-ar/", views.api_news_ar, name="api_news_ar"),
    path("healthz", views.healthz, name="healthz"),
]
