"""Errores públicos sin detalles internos."""
from api.responses import error_response

def server_error(request):
    response = error_response(
        "SERVICIO_NO_DISPONIBLE", "No se pudo completar la consulta. Intentá más tarde.", status=500,
    )
    response["Cache-Control"] = "no-store"
    return response
