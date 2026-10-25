"""Rutas públicas del contrato v1."""

from django.urls import path

from . import views

app_name = "api"
urlpatterns = [
    path("health/", views.health, name="health"),
    path("clima/", views.climate, name="climate"),
    path("lugares/", views.places, name="places"),
]
