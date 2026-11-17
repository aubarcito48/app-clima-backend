"""Rutas públicas del contrato v1."""

from django.urls import path

from . import views
from .voice_views import voice
from .map_views import weather_map

app_name = "api"
urlpatterns = [
    path("mapa/", weather_map, name="weather-map"),
    path("voz/", voice, name="voice"),
    path("health/", views.health, name="health"),
    path("clima/", views.climate, name="climate"),
    path("lugares/", views.places, name="places"),
    path("alertas/", views.alerts, name="alerts"),
]
