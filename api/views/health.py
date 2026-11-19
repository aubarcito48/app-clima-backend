"""Liveness sin consultar proveedores ni persistencia."""
from api.responses import get_only, json_response

@get_only
def health(request):
    # Liveness de la aplicación: no prueba proveedores, credenciales ni BD.
    response = json_response({"estado": "ok"})
    response["Cache-Control"] = "no-store"
    return response
