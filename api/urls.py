"""Rutas públicas del contrato v1."""

from django.urls import path

from api.views.weather import climate
from api.views.places import places
from api.views.alerts import alerts
from api.views.health import health
from api.views.voice import voice
from api.views.maps import weather_map

app_name = "api"
urlpatterns = [
    path("mapa/", weather_map, name="weather-map"),
    path("voz/", voice, name="voice"),
    path("health/", health, name="health"),
    path("clima/", climate, name="climate"),
    path("lugares/", places, name="places"),
    path("alertas/", alerts, name="alerts"),
]
