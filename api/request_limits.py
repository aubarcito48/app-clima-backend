"""Límites globales y por visitante; solo admite proxies confiables explícitos."""

from collections import deque
import ipaddress
import math
import threading
import time

from django.conf import settings
from django.utils.crypto import salted_hmac

from .responses import error_response


class RequestBudget:
    def __init__(self, capacity=None):
        self._requests = {}
        self._lock = threading.Lock()
        self.capacity = capacity

    def retry_after(self, route, limit, now):
        with self._lock:
            if route not in self._requests and self.capacity and len(self._requests) >= self.capacity:
                self._requests = {key: entries for key, entries in self._requests.items()
                                  if entries and entries[-1] > now - 60}
                if len(self._requests) >= self.capacity:
                    return 60
            requests = self._requests.setdefault(route, deque())
            while requests and requests[0] <= now - 60:
                requests.popleft()
            if len(requests) >= limit:
                return max(1, math.ceil(requests[0] + 60 - now))
            requests.append(now)
            return 0


def visitor_key(request):
    address = request.META.get('REMOTE_ADDR', '')
    hops = settings.API_TRUSTED_PROXY_HOPS
    if hops:
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
        parts = forwarded.split(',') if len(forwarded) <= 2048 else []
        address = parts[-hops].strip() if len(parts) >= hops else ''
    try:
        ip = ipaddress.ip_address(address)
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        # Privacy addresses within one IPv6 /64 share an allowance.
        address = str(ipaddress.ip_network(f'{ip}/64', strict=False)) if ip.version == 6 else str(ip)
    except ValueError:
        address = 'unknown'
    return salted_hmac('api-visitor-limit', address).hexdigest()


def limit_response(retry):
    response = error_response('LIMITE_ALCANZADO',
        'Se alcanzó el límite de consultas. Volvé a intentar en unos segundos.', status=429)
    response['Retry-After'] = str(retry)
    response['Cache-Control'] = 'no-store'
    return response


class ApiRequestLimitsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.budget = RequestBudget()
        self.visitors = RequestBudget(capacity=settings.API_VISITOR_MAX_ENTRIES)

    def __call__(self, request):
        limits = settings.API_REQUESTS_PER_MINUTE
        limit = limits.get(request.path)
        if limit and request.method in ('GET', 'POST'):
            if len(request.META.get('QUERY_STRING', '')) > 2048:
                return error_response('ENTRADA_INVALIDA', 'La consulta es demasiado larga.', status=414)
            if settings.API_RATE_LIMIT_ENABLED:
                visitor_limit = settings.API_VISITOR_REQUESTS_PER_MINUTE.get(request.path)
                if visitor_limit:
                    retry = self.visitors.retry_after(
                        (request.path, visitor_key(request)), visitor_limit, time.monotonic())
                    if retry:
                        return limit_response(retry)
                retry = self.budget.retry_after(request.path, limit, time.monotonic())
                if retry:
                    return limit_response(retry)
        return self.get_response(request)
