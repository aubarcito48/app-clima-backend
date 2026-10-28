"""Presupuesto global de solicitudes por proceso; no confía en IPs del cliente."""

from collections import deque
import math
import threading
import time

from django.conf import settings

from .responses import error_response


class RequestBudget:
    def __init__(self):
        self._requests = {}
        self._lock = threading.Lock()

    def retry_after(self, route, limit, now):
        with self._lock:
            requests = self._requests.setdefault(route, deque())
            while requests and requests[0] <= now - 60:
                requests.popleft()
            if len(requests) >= limit:
                return max(1, math.ceil(requests[0] + 60 - now))
            requests.append(now)
            return 0


class ApiRequestLimitsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.budget = RequestBudget()

    def __call__(self, request):
        limits = settings.API_REQUESTS_PER_MINUTE
        limit = limits.get(request.path)
        if limit and request.method in ('GET', 'POST'):
            if len(request.META.get('QUERY_STRING', '')) > 2048:
                return error_response('ENTRADA_INVALIDA', 'La consulta es demasiado larga.', status=414)
            if settings.API_RATE_LIMIT_ENABLED:
                retry = self.budget.retry_after(request.path, limit, time.monotonic())
                if retry:
                    response = error_response('LIMITE_ALCANZADO',
                        'Se alcanzó el límite de consultas. Volvé a intentar en unos segundos.', status=429)
                    response['Retry-After'] = str(retry)
                    response['Cache-Control'] = 'no-store'
                    return response
        return self.get_response(request)
