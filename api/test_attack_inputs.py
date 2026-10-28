"""Ataques reproducibles locales; no se consulta ningún proveedor real."""

from concurrent.futures import ThreadPoolExecutor
import json
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from django.test import SimpleTestCase, override_settings

from .request_limits import RequestBudget
from .services.openweather import request_json
from .test_voice import sample_wav


class HostileVoiceInputTests(SimpleTestCase):
    @patch('api.voice_views.synthesize', return_value=sample_wav())
    def test_malformed_nested_duplicate_and_unicode_inputs_never_start_synthesis(self, synth):
        bodies = ['{"texto":"uno","texto":"dos"}', '[' * 1500 + '0' + ']' * 1500,
                  '{', 'null', '{"texto":"hola","modelo":"../otro"}',
                  json.dumps({'texto': '\ud800'}), json.dumps({'texto': '\udfff'}),
                  json.dumps({'texto': '\u200b'}), json.dumps({'texto': 'hola\u202emundo'}),
                  json.dumps({'texto': 'a' * 601})]
        for body in bodies:
            with self.subTest(body_length=len(body)):
                response = self.client.post('/api/v1/voz/', body, content_type='application/json')
                self.assertEqual(response.status_code, 400)
        synth.assert_not_called()

    @patch('api.voice_views.synthesize')
    def test_oversized_body_is_rejected_without_parsing_or_synthesizing(self, synth):
        with patch('api.voice_views.json.loads', side_effect=AssertionError('Must not parse')):
            response = self.client.post('/api/v1/voz/', 'x' * 100000, content_type='application/json')
        self.assertEqual(response.status_code, 413)
        synth.assert_not_called()


@override_settings(API_RATE_LIMIT_ENABLED=True, API_REQUESTS_PER_MINUTE={'/api/v1/voz/': 2})
class PublicRequestBudgetTests(SimpleTestCase):
    @patch('api.voice_views.synthesize', return_value=sample_wav())
    def test_spoofed_ips_and_origins_do_not_bypass_shared_budget(self, synth):
        for i in range(4):
            response = self.client.post('/api/v1/voz/', json.dumps({'texto': 'Hola, Isa.'}),
                content_type='application/json', HTTP_X_FORWARDED_FOR=f'192.0.2.{i}',
                HTTP_ORIGIN=f'https://other-{i}.invalid', REMOTE_ADDR=f'198.51.100.{i}')
            self.assertEqual(response.status_code, 200 if i < 2 else 429)
        self.assertEqual(synth.call_count, 2)
        self.assertGreater(int(response['Retry-After']), 0)
        self.assertEqual(response.json()['codigo'], 'LIMITE_ALCANZADO')
        self.assertIn('no-store', response['Cache-Control'])
        for _ in range(4):
            self.assertEqual(self.client.get('/api/v1/health/').status_code, 200)

    def test_parallel_requests_share_one_atomic_window_and_recover(self):
        budget = RequestBudget()
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: budget.retry_after('/api/v1/voz/', 3, 100), range(20)))
        self.assertEqual(results.count(0), 3)
        self.assertEqual(results.count(60), 17)
        self.assertEqual(budget.retry_after('/api/v1/voz/', 3, 159), 1)
        self.assertEqual(budget.retry_after('/api/v1/voz/', 3, 160), 0)

    @patch('api.views.query_climate')
    def test_long_query_and_duplicate_fields_never_reach_provider(self, query):
        self.assertEqual(self.client.get('/api/v1/clima/?ciudad=a&ciudad=b').status_code, 400)
        with override_settings(API_REQUESTS_PER_MINUTE={'/api/v1/clima/': 2}):
            self.assertEqual(self.client.get('/api/v1/clima/?ciudad=' + 'a' * 3000).status_code, 414)
        query.assert_not_called()


class ProviderDestinationTests(SimpleTestCase):
    @override_settings(OPENWEATHER_API_KEY='TEST-ONLY-KEY')
    @patch('api.services.openweather.http.client.HTTPSConnection')
    def test_host_cannot_be_changed_and_query_injection_stays_encoded(self, connection):
        client = connection.return_value
        client.getresponse.return_value.status = 200
        client.getresponse.return_value.read.return_value = b'{}'
        payload = "http://169.254.169.254/; ' OR 1=1 -- &appid=attacker"
        self.assertEqual(request_json('/geo/1.0/direct', {'q': payload}), {})
        self.assertEqual(connection.call_args.args[0], 'api.openweathermap.org')
        url = urlsplit(client.request.call_args.args[1])
        self.assertEqual(url.path, '/geo/1.0/direct')
        self.assertEqual(parse_qs(url.query), {'q': [payload], 'appid': ['TEST-ONLY-KEY']})
        with self.assertRaises(ValueError):
            request_json('http://127.0.0.1/private', {})
