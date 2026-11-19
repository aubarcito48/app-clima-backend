"""Consulta HTTP de alertas oficiales."""
from api.responses import error_response, get_only, json_response
from api.validation.alerts import AlertsQueryForm
from api.services.alerts.alerts import query_alerts

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
