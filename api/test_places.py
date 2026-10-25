import json
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.test import SimpleTestCase, override_settings
from jsonschema import Draft202012Validator
from .services.places import search_places, MAX_BYTES
from .services.geocoding import GeocodingFailure

ROW={'id':3860259,'name':'Córdoba','country_code':'AR','admin1':'Córdoba','latitude':-31.42,'longitude':-64.18}

@override_settings(ALLOWED_HOSTS=['testserver'],CORS_ALLOWED_ORIGINS=['http://localhost:4200'])
class PlaceSuggestionsTests(SimpleTestCase):
    def setUp(self):
        for target in ('socket.create_connection','socket.socket.connect','sqlite3.connect'):
            block=patch(target,side_effect=AssertionError('Sin red ni BD')); block.start(); self.addCleanup(block.stop)
        factory=patch('api.services.places.http.client.HTTPSConnection'); self.factory=factory.start(); self.addCleanup(factory.stop)
        self.connection=self.factory.return_value
        self.response=self.connection.getresponse.return_value
        self.response.status=200
        self.response.read.return_value=json.dumps({'results':[ROW]}).encode()

    def test_endpoint_uses_prefix_geocoding_without_weather_or_ai(self):
        with patch('api.services.climate.fetch_weather') as weather, patch('api.services.climate.generate_recommendation') as advice:
            response=self.client.get('/api/v1/lugares/',{'q':'  Co\u0301r  '},HTTP_ORIGIN='http://localhost:4200')
        self.assertEqual(response.status_code,200)
        schema=json.loads((Path(__file__).with_name('contracts')/'places-v1.schema.json').read_text(encoding='utf-8'))
        Draft202012Validator(schema).validate(response.json())
        self.assertEqual(response.json()['sugerencias'][0]['nombre'],'Córdoba')
        self.assertEqual(response['Cache-Control'],'no-store')
        self.assertEqual(response['Access-Control-Allow-Origin'],'http://localhost:4200')
        self.factory.assert_called_once_with('geocoding-api.open-meteo.com',timeout=3)
        target=urlsplit(self.connection.request.call_args.args[1])
        self.assertEqual(target.path,'/v1/search')
        self.assertEqual(parse_qs(target.query),{'name':['Cór'],'count':['5'],'language':['es'],'format':['json']})
        self.connection.close.assert_called_once(); weather.assert_not_called(); advice.assert_not_called()

    def test_invalid_or_duplicated_input_never_calls_the_provider(self):
        for params in ({},{'q':'co'},{'q':'x'*207},{'q':'co\x00r'},{'q':'cord','url':'https://example.invalid'}):
            self.assertEqual(self.client.get('/api/v1/lugares/',params).status_code,400)
        self.assertEqual(self.client.get('/api/v1/lugares/?q=cor&q=men').status_code,400)
        self.assertEqual(self.client.post('/api/v1/lugares/',{'q':'cor'}).status_code,405)
        self.factory.assert_not_called()

    def test_optional_country_filter_and_missing_results(self):
        self.response.read.return_value=b'{}'
        self.assertEqual(search_places('Córdoba, Córdoba, ar'),[])
        target=urlsplit(self.connection.request.call_args.args[1])
        params=parse_qs(target.query)
        self.assertEqual(params['name'],['Córdoba, Córdoba'])
        self.assertEqual(params['countryCode'],['AR'])

    def test_rate_limit_and_provider_failures_are_safe(self):
        for status in (429,301,401,500):
            self.response.status=status
            self.response.read.return_value=b'PRIVATE-KEY body'
            response=self.client.get('/api/v1/lugares/',{'q':'cord'})
            self.assertEqual(response.status_code,429 if status==429 else 503)
            self.assertNotIn('PRIVATE',response.content.decode())
        self.connection.request.side_effect=TimeoutError('PRIVATE')
        self.assertEqual(self.client.get('/api/v1/lugares/',{'q':'cord'}).status_code,503)

    def test_invalid_payloads_are_rejected_and_ids_deduplicated(self):
        for body in (b'not json',b'{"results":NaN}',b'x'*(MAX_BYTES+1),json.dumps({'results':[{}]}).encode(),json.dumps({'results':[{**ROW,'latitude':999}]}).encode(),json.dumps({'results':[ROW]*6}).encode()):
            self.response.read.return_value=body
            with self.assertRaises(GeocodingFailure): search_places('cord')
        self.response.read.return_value=json.dumps({'results':[ROW,ROW]}).encode()
        self.assertEqual(len(search_places('cord')),1)
