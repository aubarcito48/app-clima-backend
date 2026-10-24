"""Orquestación de una consulta, sin estado compartido ni persistencia."""

from django.utils import timezone

from .geocoding import resolve_location
from .recommendations import generate_recommendation
from .weather import fetch_weather


def query_climate(query):
    consulted_at = timezone.now()
    location = resolve_location(query)
    snapshot = fetch_weather(location)
    recommendation = generate_recommendation(snapshot)
    return {
        "ubicacion": snapshot.ubicacion,
        "actual": snapshot.actual,
        "pronostico": snapshot.pronostico,
        "recomendacion": recommendation,
        "meta": {
            "fuente_meteorologica": "OpenWeather",
            "consultado_en_utc": consulted_at.isoformat().replace("+00:00", "Z"),
            "unidades": {"temperatura": "°C", "viento": "km/h", "humedad": "%", "fecha": "UTC"},
        },
    }
