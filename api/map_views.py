"""Small, fixed-host tile proxy. OpenWeather credentials never reach the browser."""

from collections import OrderedDict
import threading
import time

from django.conf import settings
from django.http import HttpResponse
import httpx

from .responses import error_response, get_only


LAYERS = {'temperature': 'temp_new', 'rain': 'precipitation_new', 'wind': 'wind_new'}
_tiles = OrderedDict()
_lock = threading.Lock()
_cooldown_until = 0
MAX_TILE_BYTES = 128 * 1024


def _tile(layer, z, x, y):
    global _cooldown_until
    key = (layer, z, x, y)
    with _lock:
        now = time.monotonic()
        cached = _tiles.get(key)
        if cached and cached[0] > now:
            _tiles.move_to_end(key)
            return cached[1]
        if now < _cooldown_until:
            raise ValueError('Tile provider cooling down')
        try:
            url = f'https://tile.openweathermap.org/map/{LAYERS[layer]}/{z}/{x}/{y}.png'
            with httpx.Client(timeout=httpx.Timeout(3, connect=2), trust_env=False,
                              follow_redirects=False) as client:
                with client.stream('GET', url, params={'appid': settings.OPENWEATHER_API_KEY},
                                   headers={'Accept': 'image/png'}) as response:
                    response.raise_for_status()
                    if response.headers.get('content-type', '').split(';')[0] != 'image/png':
                        raise ValueError('Unexpected tile type')
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_TILE_BYTES:
                            raise ValueError('Oversized tile')
            if not body.startswith(b'\x89PNG\r\n\x1a\n'):
                raise ValueError('Invalid tile')
            data = bytes(body)
            _tiles[key] = (time.monotonic() + 300, data)
            _tiles.move_to_end(key)
            while len(_tiles) > 32:
                _tiles.popitem(last=False)
            return data
        except (httpx.HTTPError, ValueError, OSError):
            _cooldown_until = time.monotonic() + 30
            raise


@get_only
def weather_map(request):
    try:
        if set(request.GET) != {'layer', 'z', 'x', 'y'} or any(
                len(request.GET.getlist(name)) != 1 for name in request.GET):
            raise ValueError()
        layer = request.GET['layer']
        if layer not in LAYERS:
            raise ValueError()
        values = [request.GET[name] for name in ('z', 'x', 'y')]
        if any(not value.isascii() or not value.isdecimal() or len(value) > 3 for value in values):
            raise ValueError()
        z, x, y = map(int, values)
        if not 3 <= z <= 8 or not 0 <= x < 2**z or not 0 <= y < 2**z:
            raise ValueError()
    except (ValueError, KeyError):
        return error_response('ENTRADA_INVALIDA', 'Mapa o coordenadas no válidos.', status=400)
    try:
        if not settings.OPENWEATHER_API_KEY.strip():
            raise ValueError('Missing provider key')
        response = HttpResponse(_tile(layer, z, x, y), content_type='image/png')
        response['Cache-Control'] = 'public, max-age=300'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    except (httpx.HTTPError, ValueError, OSError):
        response = error_response('MAPA_NO_DISPONIBLE', 'El mapa no está disponible por el momento.', status=503)
        response['Cache-Control'] = 'no-store'
        response['Retry-After'] = '30'
        return response
