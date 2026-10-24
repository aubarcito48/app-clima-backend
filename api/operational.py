"""Registros de campos permitidos; nunca serializar request, msg o exc_info."""

import json
import logging
from time import monotonic


class SafeOperationalFormatter(logging.Formatter):
    def format(self, record):
        status = getattr(record, "status_code", None)
        duration = getattr(record, "duration_ms", None)
        route = getattr(record, "api_route", "other")
        return json.dumps({
            "event": "http_response" if record.name == "api.operations" else "application",
            "level": record.levelname if record.levelno in {10, 20, 30, 40, 50} else "UNKNOWN",
            "route": route if route in {"health", "climate"} else "other",
            "status": status if type(status) is int and 100 <= status <= 599 else None,
            "duration_ms": duration if type(duration) is int and 0 <= duration <= 86400000 else None,
        })


class OperationalMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = monotonic()
        response = self.get_response(request)
        route = {"/api/v1/health/": "health", "/api/v1/clima/": "climate"}.get(request.path, "other")
        logging.getLogger("api.operations").info("http_response", extra={
            "api_route": route, "status_code": response.status_code,
            "duration_ms": max(0, int((monotonic() - started) * 1000)),
        })
        if request.path.startswith("/api/"):
            response["Cache-Control"] = "no-store"
        return response
