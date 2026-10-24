"""Entrada HTTP del contrato v1 con errores públicos y disponibilidad parcial."""

from .responses import error_response, get_only, json_response
from .validation import ClimateQueryForm
from .services.climate import query_climate
from .services.geocoding import AmbiguousLocation, GeocodingFailure
from .services.weather import WeatherFailure


def server_error(request):
    response = error_response(
        "SERVICIO_NO_DISPONIBLE", "No se pudo completar la consulta. Intentá más tarde.", status=500,
    )
    response["Cache-Control"] = "no-store"
    return response


@get_only
def health(request):
    # Liveness de la aplicación: no prueba proveedores, credenciales ni BD.
    response = json_response({"estado": "ok"})
    response["Cache-Control"] = "no-store"
    return response


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
