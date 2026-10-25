"""Clima y pronóstico normalizados. La composición HTTP se realizará en TK07."""

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import unicodedata

from .geocoding import GeoLocation
from .openweather import OpenWeatherRateLimited, OpenWeatherUnavailable, request_json


CURRENT_PATH = "/data/2.5/weather"
FORECAST_PATH = "/data/2.5/forecast"
MAX_FORECAST_INTERVALS = 40


class WeatherFailure(Exception):
    status = 503
    code = "SERVICIO_NO_DISPONIBLE"
    message = "No se pudo obtener el clima actual. Intentá más tarde."

    def __init__(self):
        super().__init__(self.message)


class WeatherRateLimited(WeatherFailure):
    status = 429
    code = "LIMITE_ALCANZADO"
    message = "Se alcanzó el límite de consultas meteorológicas. Intentá más tarde."


@dataclass(frozen=True)
class CurrentWeather:
    actual: dict
    desplazamiento_horario_segundos: int


@dataclass(frozen=True)
class WeatherSnapshot:
    ubicacion: dict
    actual: dict
    pronostico: dict


def _number(value, *, optional=False, minimum=None, maximum=None):
    if value is None and optional:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WeatherFailure()
    try:
        finite = math.isfinite(value)
    except OverflowError:
        raise WeatherFailure() from None
    if (
        not finite or (minimum is not None and value < minimum)
        or (maximum is not None and value > maximum)
    ):
        raise WeatherFailure()
    return value


def _utc_timestamp(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise WeatherFailure()
    try:
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except (ValueError, OverflowError, OSError):
        raise WeatherFailure() from None


def _timezone_offset(value):
    if isinstance(value, bool) or not isinstance(value, int) or not -50400 <= value <= 50400:
        raise WeatherFailure()
    return value


def _description(weather):
    if weather is None or weather == []:
        return None
    if not isinstance(weather, list) or not all(isinstance(item, dict) for item in weather):
        raise WeatherFailure()
    value = weather[0].get("description")
    if value is None:
        return None
    if not isinstance(value, str):
        raise WeatherFailure()
    result = unicodedata.normalize("NFC", " ".join(value.split()))
    if any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in result):
        raise WeatherFailure()
    return result or None


def _payload(payload):
    if not isinstance(payload, dict):
        raise WeatherFailure()
    code = payload.get("cod", 200)
    if code in (429, "429"):
        raise WeatherRateLimited()
    if code not in (200, "200"):
        raise WeatherFailure()
    return payload


def _weather_icon(weather):
    if not isinstance(weather, list) or not weather or not isinstance(weather[0], dict):
        return {}
    value = weather[0].get("icon")
    allowed = {code + period for code in ("01", "02", "03", "04", "09", "10", "11", "13", "50") for period in ("d", "n")}
    return {"icono": value} if isinstance(value, str) and value in allowed else {}


def normalize_current(payload):
    payload = _payload(payload)
    solar = payload.get("sys")
    solar_fields = {}
    if isinstance(solar, dict):
        for provider_key, field in (("sunrise", "amanecer_utc"), ("sunset", "atardecer_utc")):
            if solar.get(provider_key) is not None:
                solar_fields[field] = _utc_timestamp(solar[provider_key])
    main = payload.get("main")
    if not isinstance(main, dict):
        raise WeatherFailure()
    wind = payload.get("wind")
    if wind is not None and not isinstance(wind, dict):
        raise WeatherFailure()
    speed = _number(wind.get("speed") if wind else None, optional=True, minimum=0)
    wind_kmh = None if speed is None else _number(round(speed * 3.6, 3), minimum=0)
    return CurrentWeather(
        actual={
            "fecha_utc": _utc_timestamp(payload.get("dt")),
            "temperatura_c": _number(main.get("temp")),
            "sensacion_c": _number(main.get("feels_like"), optional=True),
            "humedad_pct": _number(main.get("humidity"), optional=True, minimum=0, maximum=100),
            "viento_kmh": wind_kmh,
            "descripcion": _description(payload.get("weather")),
            **solar_fields,
            **_weather_icon(payload.get("weather")),
        },
        desplazamiento_horario_segundos=_timezone_offset(payload.get("timezone")),
    )


def normalize_forecast(payload):
    payload = _payload(payload)
    rows = payload.get("list")
    if not isinstance(rows, list) or len(rows) > MAX_FORECAST_INTERVALS:
        raise WeatherFailure()
    if "cnt" in payload and (
        isinstance(payload["cnt"], bool) or not isinstance(payload["cnt"], int)
        or payload["cnt"] != len(rows)
    ):
        raise WeatherFailure()
    intervals = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("main"), dict):
            raise WeatherFailure()
        date = _utc_timestamp(row.get("dt"))
        if date in seen:
            raise WeatherFailure()
        seen.add(date)
        wind = row.get("wind")
        if wind is not None and not isinstance(wind, dict):
            raise WeatherFailure()
        speed = _number(wind.get("speed") if wind else None, optional=True, minimum=0)
        intervals.append({
            "fecha_utc": date,
            "temperatura_c": _number(row["main"].get("temp")),
            "descripcion": _description(row.get("weather")),
            **_weather_icon(row.get("weather")),
            **({"viento_kmh": _number(round(speed * 3.6, 3), minimum=0)} if speed is not None else {}),
            **({"precipitacion_pct": round(_number(row["pop"], minimum=0, maximum=1) * 100, 2)}
               if row.get("pop") is not None else {}),
        })
    intervals.sort(key=lambda interval: datetime.fromisoformat(interval["fecha_utc"]))
    return {"estado": "disponible" if intervals else "no_disponible", "intervalos": intervals}


class OpenWeatherMeteorology:
    def _fetch(self, path, location: GeoLocation):
        # También valida coordenadas si el servicio se llama fuera del geocodificador.
        latitude = _number(location.latitud, minimum=-90, maximum=90)
        longitude = _number(location.longitud, minimum=-180, maximum=180)
        try:
            return request_json(path, {
                "lat": latitude, "lon": longitude, "units": "metric", "lang": "es",
            })
        except OpenWeatherRateLimited:
            raise WeatherRateLimited() from None
        except OpenWeatherUnavailable:
            raise WeatherFailure() from None

    def current(self, location):
        return self._fetch(CURRENT_PATH, location)

    def forecast(self, location):
        return self._fetch(FORECAST_PATH, location)


def fetch_weather(location: GeoLocation, *, client=None):
    client = client if client is not None else OpenWeatherMeteorology()
    # Si falla el clima actual, se propaga el error y no se pide el pronóstico.
    current = normalize_current(client.current(location))
    try:
        forecast = normalize_forecast(client.forecast(location))
    except WeatherFailure:
        forecast = {"estado": "no_disponible", "intervalos": []}
    return WeatherSnapshot(
        ubicacion={
            **location.as_candidate(),
            "desplazamiento_horario_segundos": current.desplazamiento_horario_segundos,
        },
        actual=current.actual,
        pronostico=forecast,
    )
