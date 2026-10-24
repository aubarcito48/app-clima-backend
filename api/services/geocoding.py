"""Geocodificación con destino fijo y resultados validados, sin persistencia."""

from dataclasses import asdict, dataclass
import http.client
import json
import math
import re
import unicodedata
from urllib.parse import urlencode

from django.conf import settings

from api.validation import ClimateQuery


GEOCODING_HOST = "api.openweathermap.org"
GEOCODING_PATH = "/geo/1.0/direct"
RESULT_LIMIT = 5
MAX_RESPONSE_BYTES = 256 * 1024


class GeocodingFailure(Exception):
    code = "SERVICIO_NO_DISPONIBLE"
    status = 503
    message = "No se pudo consultar la ubicación en este momento. Intentá más tarde."

    def __init__(self):
        # Nunca conservar URL, appid, cuerpo del proveedor o excepción original en args.
        super().__init__(self.message)


class LocationNotFound(GeocodingFailure):
    code = "CIUDAD_NO_ENCONTRADA"
    status = 404
    message = "No encontramos una ubicación para esa consulta. Revisá la ciudad, el país o la región."


class GeocodingRateLimited(GeocodingFailure):
    code = "LIMITE_ALCANZADO"
    status = 429
    message = "Se alcanzó el límite de consultas de ubicación. Intentá más tarde."


class IncompleteLocationSearch(GeocodingFailure):
    message = "No pudimos determinar una ubicación con certeza. Precisá la ciudad, el país o la región."


class AmbiguousLocation(GeocodingFailure):
    code = "CIUDAD_AMBIGUA"
    status = 409
    message = "Hay varias ubicaciones posibles. Precisá el país o la región."

    def __init__(self, candidates):
        self.candidates = tuple(candidates)
        super().__init__()


@dataclass(frozen=True)
class GeoLocation:
    nombre: str
    pais: str
    region: str | None
    latitud: float
    longitud: float

    def as_candidate(self):
        return asdict(self)


def _invalid_json_constant(value):
    raise ValueError("Número no válido en JSON del proveedor.")


class OpenWeatherGeocoding:
    def search(self, query: ClimateQuery):
        key = settings.OPENWEATHER_API_KEY.strip()
        if not key:
            raise GeocodingFailure()

        # OpenWeather admite state code solo para EE. UU. No se envía una región
        # libre en esa posición: se filtra contra state en la respuesta validada.
        location_name = query.ciudad + (f",{query.pais}" if query.pais else "")
        params = urlencode({"q": location_name, "limit": RESULT_LIMIT, "appid": key})
        connection = http.client.HTTPSConnection(
            GEOCODING_HOST, timeout=settings.OPENWEATHER_CONNECT_TIMEOUT_SECONDS
        )
        try:
            connection.connect()
            if connection.sock is None:
                raise GeocodingFailure()
            connection.sock.settimeout(settings.OPENWEATHER_READ_TIMEOUT_SECONDS)
            connection.request(
                "GET", f"{GEOCODING_PATH}?{params}",
                headers={"Accept": "application/json"},
            )
            response = connection.getresponse()
            if response.status == 429:
                raise GeocodingRateLimited()
            if response.status != 200:
                # No seguir redirecciones ni reenviar errores/cuerpos con la clave.
                raise GeocodingFailure()
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise GeocodingFailure()
            payload = json.loads(body.decode("utf-8"), parse_constant=_invalid_json_constant)
            if not isinstance(payload, list) or len(payload) > RESULT_LIMIT:
                raise GeocodingFailure()
            return payload
        except (OSError, http.client.HTTPException, ValueError):
            raise GeocodingFailure() from None
        finally:
            connection.close()


def _text(value, *, optional=False):
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise GeocodingFailure()
    result = unicodedata.normalize("NFC", " ".join(value.split()))
    if not result and optional:
        return None
    if (
        not result or len(result) > 100
        or any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in result)
    ):
        raise GeocodingFailure()
    return result


def _coordinate(value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GeocodingFailure()
    if not minimum <= value <= maximum or not math.isfinite(value):
        raise GeocodingFailure()
    return float(value)


def _parse_location(item):
    if not isinstance(item, dict):
        raise GeocodingFailure()
    name = _text(item.get("name"))
    local_names = item.get("local_names")
    if isinstance(local_names, dict) and local_names.get("es"):
        name = _text(local_names["es"])
    country = _text(item.get("country"))
    if not re.fullmatch(r"[A-Za-z]{2}", country):
        raise GeocodingFailure()
    return GeoLocation(
        nombre=name,
        pais=country.upper(),
        region=_text(item.get("state"), optional=True),
        latitud=_coordinate(item.get("lat"), -90, 90),
        longitud=_coordinate(item.get("lon"), -180, 180),
    )


def _region_key(value):
    return "".join(
        char for char in unicodedata.normalize("NFD", " ".join(value.split()).casefold())
        if unicodedata.category(char) != "Mn"
    )


def resolve_location(query: ClimateQuery, *, client=None):
    payload = (client if client is not None else OpenWeatherGeocoding()).search(query)
    if not isinstance(payload, list) or len(payload) > RESULT_LIMIT:
        raise GeocodingFailure()

    # Validar todo antes de filtrar. Una fila dañada no puede ocultar ambigüedad.
    locations = [_parse_location(item) for item in payload]
    unique = {}
    for location in locations:
        if query.pais and location.pais != query.pais:
            continue
        if query.region and (
            location.region is None or _region_key(location.region) != _region_key(query.region)
        ):
            continue
        identity = (location.pais, location.latitud, location.longitud)
        previous = unique.get(identity)
        if previous is None or (previous.region is None and location.region is not None):
            unique[identity] = location

    candidates = list(unique.values())
    if len(candidates) > 1:
        raise AmbiguousLocation(candidates)
    if len(payload) == RESULT_LIMIT:
        # El proveedor pudo truncar resultados: cero/uno tras filtrar no garantiza
        # ausencia/unicidad. No afirmar 404 ni seleccionar silenciosamente.
        raise IncompleteLocationSearch()
    if not candidates:
        raise LocationNotFound()
    return candidates[0]
