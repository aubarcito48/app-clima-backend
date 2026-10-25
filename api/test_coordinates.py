import json
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.test import SimpleTestCase, override_settings
from jsonschema import Draft202012Validator

from .validation import ClimateQueryForm, CoordinatesQuery
from .services.geocoding import resolve_coordinates, GeocodingFailure, GeocodingRateLimited, LocationNotFound
from .services.openweather import OpenWeatherUnavailable, OpenWeatherRateLimited
from .test_climate import CURRENT, FORECAST, GEO_ROWS


@override_settings(OPENWEATHER_API_KEY='DUMMY-KEY', GROQ_API_KEY='', GROQ_MODEL='', ALLOWED_HOSTS=['testserver'])
class CoordinatesTests(SimpleTestCase):
    def setUp(self):
        for target in ('socket.socket.connect', 'socket.create_connection', 'sqlite3.connect'):
            block = patch(target, side_effect=AssertionError('Sin red ni BD'))
            block.start(); self.addCleanup(block.stop)

    def test_zero_coordinates_and_valid_boundaries(self):
        for lat, lon in ((0, 0), (-90, -180), (90, 180), (-31.42, -64.18)):
            with self.subTest(lat=lat, lon=lon):
                form = ClimateQueryForm({'latitud': str(lat), 'longitud': str(lon)})
                self.assertEqual(form.query(), CoordinatesQuery(lat, lon))

    def test_invalid_coordinates_never_call_providers_and_errors_conform_to_schema(self):
        schema = json.loads((Path(__file__).with_name('contracts') / 'response-v1.schema.json').read_text(encoding='utf-8'))
        with patch('api.services.climate.resolve_coordinates') as resolver:
            for params in ({'latitud':'0'}, {'longitud':'0'}, {'latitud':'nan','longitud':'0'}, {'latitud':'0','longitud':'inf'}, {'latitud':'91','longitud':'0'}, {'latitud':'0','longitud':'-181'}, {'latitud':'0','longitud':'0','ciudad':'Córdoba'}, {'latitud':'0','longitud':'0','pais':'AR'}):
                with self.subTest(params=params):
                    response = self.client.get('/api/v1/clima/', params)
                    self.assertEqual(response.status_code, 400)
                    Draft202012Validator(schema).validate(response.json())
            self.assertEqual(self.client.get('/api/v1/clima/?latitud=0&latitud=1&longitud=0').status_code, 400)
            resolver.assert_not_called()

    def test_http_response_uses_requested_point_instead_of_nearest_city_center(self):
        with patch('api.services.geocoding.request_json', return_value=[GEO_ROWS[0]]) as geo, patch('api.services.weather.request_json', side_effect=[CURRENT, FORECAST]) as weather:
            response = self.client.get('/api/v1/clima/', {'latitud':'-31.123456','longitud':'-64.654321'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['ubicacion']['nombre'], 'Córdoba')
        self.assertEqual(response.json()['ubicacion']['latitud'], -31.123456)
        self.assertEqual(response.json()['ubicacion']['longitud'], -64.654321)
        self.assertEqual(response.json()['recomendacion']['estado'], 'no_disponible')
        geo.assert_called_once_with('/geo/1.0/reverse', {'lat':-31.123456,'lon':-64.654321,'limit':1})
        for call in weather.call_args_list:
            self.assertEqual(call.args[1]['lat'], -31.123456)
            self.assertEqual(call.args[1]['lon'], -64.654321)

    def test_reverse_geocoding_failures_are_controlled(self):
        for failure, expected in ((OpenWeatherUnavailable(), GeocodingFailure), (OpenWeatherRateLimited(), GeocodingRateLimited)):
            with patch('api.services.geocoding.request_json', side_effect=failure), self.assertRaises(expected):
                resolve_coordinates(CoordinatesQuery(0, 0))
        for payload, expected in (([], LocationNotFound), ({}, GeocodingFailure), ([{}], GeocodingFailure), (GEO_ROWS, GeocodingFailure)):
            with patch('api.services.geocoding.request_json', return_value=payload), self.assertRaises(expected):
                resolve_coordinates(CoordinatesQuery(0, 0))

    def test_reverse_transport_has_fixed_host_path_key_and_no_retry(self):
        with patch('api.services.openweather.http.client.HTTPSConnection') as factory:
            connection = factory.return_value
            connection.getresponse.return_value.status = 200
            connection.getresponse.return_value.read.return_value = json.dumps([GEO_ROWS[0]]).encode()
            location = resolve_coordinates(CoordinatesQuery(0, 0))
            self.assertEqual(location.latitud, 0)
            self.assertEqual(factory.call_args.args, ('api.openweathermap.org',))
            target = urlsplit(connection.request.call_args.args[1])
            self.assertEqual(target.path, '/geo/1.0/reverse')
            self.assertEqual(parse_qs(target.query), {'lat':['0'], 'lon':['0'], 'limit':['1'], 'appid':['DUMMY-KEY']})
            connection.request.assert_called_once()
            connection.close.assert_called_once()
