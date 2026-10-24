"""Entrada HTTP. La integración con proveedores comienza en las tareas siguientes."""

from .responses import error_response, get_only, json_response
from .validation import ClimateQueryForm
from .services.geocoding import AmbiguousLocation, GeocodingFailure, resolve_location


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
        # La ubicación resuelta se usará para consultar el clima en TK05–TK07.
        resolve_location(form.query())
    except GeocodingFailure as failure:
        candidates = (
            [location.as_candidate() for location in failure.candidates]
            if isinstance(failure, AmbiguousLocation) else None
        )
        return error_response(
            failure.code, failure.message, status=failure.status, candidates=candidates
        )

    # Resolver una ubicación todavía no entrega clima ni recomendaciones.
    return error_response(
        "SERVICIO_NO_DISPONIBLE",
        "El servicio de clima todavía no está disponible. Intentá más tarde.",
        status=503,
    )
