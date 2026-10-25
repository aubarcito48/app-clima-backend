"""Orquestación de una consulta, sin estado compartido ni persistencia."""

from django.utils import timezone

from .geocoding import resolve_location, resolve_coordinates
from api.validation import CoordinatesQuery
from .recommendations import generate_recommendation
from .weather import fetch_weather


def query_climate(query):
    consulted_at = timezone.now()
    location = resolve_coordinates(query) if isinstance(query, CoordinatesQuery) else resolve_location(query)
    # Keep Spanish as the default for existing API consumers.
    if query.idioma == 'en':
        snapshot = fetch_weather(location, language='en')
        recommendation = generate_recommendation(snapshot, language='en')
    else:
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
