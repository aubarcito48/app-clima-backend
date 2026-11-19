"""Tile validation, provider isolation and bounded caching; no real network."""

from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
import httpx

from api.views import maps as map_views


PNG = b'\x89PNG\r\n\x1a\n' + b'synthetic-png-test'


@override_settings(ALLOWED_HOSTS=['testserver'], OPENWEATHER_API_KEY='PRIVATE-MAP-KEY')
class WeatherMapTests(SimpleTestCase):
    def setUp(self):
        map_views._tiles.clear()
        map_views._cooldown_until = 0
        self.addCleanup(map_views._tiles.clear)
        self.addCleanup(setattr, map_views, '_cooldown_until', 0)
        self.calls = []
        self.status, self.body, self.content_type = 200, PNG, 'image/png'
        original = httpx.Client
        def respond(request):
            self.calls.append(request)
            return httpx.Response(self.status, content=self.body,
                                  headers={'content-type': self.content_type})
        def client(**kwargs):
            self.assertFalse(kwargs['trust_env'])
            self.assertFalse(kwargs['follow_redirects'])
            return original(**kwargs, transport=httpx.MockTransport(respond))
        patcher = patch('api.views.maps.httpx.Client', side_effect=client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def query(self, **params):
        return self.client.get('/api/v1/mapa/', {'layer': 'temperature', 'z': '5', 'x': '10', 'y': '18', **params})

    def test_png_is_cached_and_credentials_never_returned(self):
        for _ in range(2):
            response = self.query()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, PNG)
            self.assertEqual(response['Content-Type'], 'image/png')
            self.assertEqual(response['Cache-Control'], 'public, max-age=300')
            self.assertNotIn(b'PRIVATE-MAP-KEY', response.content)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0].url.host, 'tile.openweathermap.org')
        self.assertEqual(self.calls[0].url.path, '/map/temp_new/5/10/18.png')
        self.assertEqual(self.calls[0].url.params['appid'], 'PRIVATE-MAP-KEY')

    def test_invalid_layers_coordinates_duplicate_and_unknown_fields_do_not_call_provider(self):
        for params in ({'layer': '../private'}, {'url': 'http://127.0.0.1'}, {'z': 9},
                       {'x': -1}, {'y': 32}, {'z': 'NaN'}, {'x': '1.2'}, {'x': '9999'}):
            self.assertEqual(self.query(**params).status_code, 400)
        self.assertEqual(self.client.get('/api/v1/mapa/?layer=rain&layer=wind&z=5&x=1&y=2').status_code, 400)
        self.assertEqual(self.client.post('/api/v1/mapa/').status_code, 405)
        self.assertEqual(self.calls, [])

    def test_provider_rejection_is_not_leaked_and_blocks_a_burst(self):
        self.status, self.body = 403, b'PRIVATE-MAP-KEY'
        response = self.query()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b'PRIVATE-MAP-KEY', response.content)
        self.assertEqual(response['Retry-After'], '30')
        self.assertEqual(self.query(x=11).status_code, 503)
        self.assertEqual(len(self.calls), 1)

    def test_non_png_oversized_and_redirect_responses_are_rejected(self):
        for status, body, content_type in ((200, b'<html>not a tile', 'text/html'),
                (200, PNG + b'x'*map_views.MAX_TILE_BYTES, 'image/png'),
                (200, b'wrong signature', 'image/png'), (302, PNG, 'image/png')):
            map_views._cooldown_until = 0
            self.status, self.body, self.content_type = status, body, content_type
            self.assertEqual(self.query().status_code, 503)

    @override_settings(OPENWEATHER_API_KEY='')
    def test_no_key_keeps_the_map_unavailable_without_a_provider_request(self):
        self.assertEqual(self.query().status_code, 503)
        self.assertEqual(self.calls, [])

    def test_cache_memory_is_bounded(self):
        for x in range(33):
            self.assertEqual(self.query(z=6, x=x).status_code, 200)
        self.assertEqual(len(map_views._tiles), 32)
