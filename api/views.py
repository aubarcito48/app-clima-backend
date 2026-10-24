"""Entrada HTTP. La integración con proveedores comienza en las tareas siguientes."""

from .responses import error_response, get_only, json_response
from .validation import ClimateQueryForm


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

    # TK03 solo valida el contrato de entrada. No inventa clima ni llama a APIs.
    # TK04–TK07 usarán form.query() para resolver y componer la respuesta real.
    return error_response(
        "SERVICIO_NO_DISPONIBLE",
        "El servicio de clima todavía no está disponible. Intentá más tarde.",
        status=503,
    )
