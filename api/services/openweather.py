"""Transporte HTTPS compartido para los endpoints fijos de OpenWeather."""

import http.client
import json
from urllib.parse import urlencode

from django.conf import settings


OPENWEATHER_HOST = "api.openweathermap.org"
ALLOWED_PATHS = frozenset({"/geo/1.0/direct", "/data/2.5/weather", "/data/2.5/forecast"})
MAX_RESPONSE_BYTES = 256 * 1024


class OpenWeatherUnavailable(Exception):
    def __init__(self):
        super().__init__("No se pudo consultar el proveedor meteorológico.")


class OpenWeatherRateLimited(OpenWeatherUnavailable):
    pass


def _invalid_json_constant(value):
    raise ValueError("Número no válido en JSON del proveedor.")


def request_json(path, params):
    if path not in ALLOWED_PATHS:
        raise ValueError("El destino no es un endpoint permitido de OpenWeather.")
    key = settings.OPENWEATHER_API_KEY.strip()
    if not key:
        raise OpenWeatherUnavailable()
    query_string = urlencode({**params, "appid": key})
    connection = None
    try:
        connection = http.client.HTTPSConnection(
            OPENWEATHER_HOST, timeout=settings.OPENWEATHER_CONNECT_TIMEOUT_SECONDS
        )
        connection.connect()
        if connection.sock is None:
            raise OpenWeatherUnavailable()
        connection.sock.settimeout(settings.OPENWEATHER_READ_TIMEOUT_SECONDS)
        connection.request("GET", f"{path}?{query_string}", headers={"Accept": "application/json"})
        response = connection.getresponse()
        if response.status == 429:
            raise OpenWeatherRateLimited()
        if response.status != 200:
            raise OpenWeatherUnavailable()
        body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise OpenWeatherUnavailable()
        return json.loads(body.decode("utf-8"), parse_constant=_invalid_json_constant)
    except (OSError, http.client.HTTPException, ValueError):
        raise OpenWeatherUnavailable() from None
    finally:
        if connection is not None:
            connection.close()
