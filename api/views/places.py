"""Sugerencias de lugares."""
from api.responses import error_response, get_only, json_response
from api.validation.places import PlaceSearchForm
from api.services.places.places import search_places
from api.services.places.geocoding import GeocodingFailure

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
