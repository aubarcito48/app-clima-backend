"""Entrada HTTP del contrato v1 con errores públicos y disponibilidad parcial."""

from .responses import error_response, get_only, json_response
from .validation import ClimateQueryForm, PlaceSearchForm, AlertsQueryForm
from .services.alerts import query_alerts
from .services.places import search_places
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
def alerts(request):
    form = AlertsQueryForm(request.GET)
    if not form.is_valid():
        response = error_response('ENTRADA_INVALIDA', 'Enviá latitud, longitud y país válidos, una sola vez.', status=400)
    else:
        data = form.cleaned_data
        response = json_response(query_alerts(data['latitud'], data['longitud'], data['pais'].upper()))
    response['Cache-Control'] = 'no-store'
    return response


@get_only
def places(request):
    form = PlaceSearchForm(request.GET)
    if not form.is_valid():
        response = error_response('ENTRADA_INVALIDA', 'Escribí entre 3 y 206 caracteres para buscar lugares.', status=400, errors={'consulta': ['Revisá el texto de búsqueda.']})
    else:
        try:
            response = json_response({'sugerencias': search_places(form.cleaned_data['q'])})
        except GeocodingFailure as failure:
            response = error_response(failure.code, 'No se pudieron obtener sugerencias. Podés buscar con Enter.', status=failure.status)
    response['Cache-Control'] = 'no-store'
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
