"""Respuestas JSON uniformes para los endpoints de la versión 1."""

from functools import wraps

from django.http import JsonResponse


def json_response(payload, *, status=200):
    return JsonResponse(
        payload,
        status=status,
        json_dumps_params={"ensure_ascii": False, "allow_nan": False},
    )


def error_response(code, message, *, status, errors=None, candidates=None):
    payload = {"codigo": code, "mensaje": message}
    if errors is not None:
        payload["errores"] = errors
    if candidates is not None:
        payload["candidatos"] = candidates
    return json_response(payload, status=status)


def get_only(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.method != "GET":
            response = error_response(
                "METODO_NO_PERMITIDO", "Este endpoint admite únicamente GET.", status=405
            )
            response["Allow"] = "GET"
            return response
        return view(request, *args, **kwargs)

    return wrapped
