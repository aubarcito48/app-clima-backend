"""Consulta HTTP del clima y disponibilidad parcial."""
from api.responses import error_response, get_only, json_response
from api.validation.weather import ClimateQueryForm
from api.services.weather.climate import query_climate
from api.services.places.geocoding import AmbiguousLocation
from api.services.places.geocoding import GeocodingFailure
from api.services.weather.weather import WeatherFailure

@get_only
def climate(request):
    form = ClimateQueryForm(request.GET)
    if not form.is_valid():
        return error_response(
            "ENTRADA_INVALIDA",
            "Revisá los parámetros de la consulta.",
            status=400,
            errors=form.public_errors(),
        )

    try:
        payload = query_climate(form.query())
    except GeocodingFailure as failure:
        candidates = (
            [location.as_candidate() for location in failure.candidates]
            if isinstance(failure, AmbiguousLocation) else None
        )
        return error_response(
            failure.code, failure.message, status=failure.status, candidates=candidates
        )
    except WeatherFailure as failure:
        return error_response(failure.code, failure.message, status=failure.status)

    response = json_response(payload)
    response["Cache-Control"] = "no-store"
    return response
