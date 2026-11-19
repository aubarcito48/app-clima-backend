import hashlib
import json
from pathlib import Path
import sqlite3
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from jsonschema import Draft202012Validator

from api.services.places.places import search_places
from api.services.places.place_catalog import CATALOG_PATH
from api.services.places.place_catalog import catalog_uri
from api.services.places.place_catalog import normalize_name


@override_settings(ALLOWED_HOSTS=['testserver'], CORS_ALLOWED_ORIGINS=['http://localhost:4200'])
class PlaceSuggestionsTests(SimpleTestCase):
    def setUp(self):
        for target in ('socket.create_connection', 'socket.socket.connect'):
            block = patch(target, side_effect=AssertionError('Las sugerencias no pueden abrir red'))
            block.start()
            self.addCleanup(block.stop)

    def test_endpoint_uses_local_catalog_without_weather_or_ai(self):
        with patch('api.services.weather.climate.fetch_weather') as weather, patch('api.services.weather.climate.generate_recommendation') as advice:
            response = self.client.get('/api/v1/lugares/', {'q': '  Co\u0301r  '}, HTTP_ORIGIN='http://localhost:4200')
        self.assertEqual(response.status_code, 200)
        schema = json.loads(((Path(__file__).resolve().parents[2] / 'contracts') / 'places-v1.schema.json').read_text(encoding='utf-8'))
        Draft202012Validator(schema).validate(response.json())
        self.assertEqual(response.json()['sugerencias'][0]['nombre'], 'Córdoba')
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(response['Access-Control-Allow-Origin'], 'http://localhost:4200')
        weather.assert_not_called()
        advice.assert_not_called()

    def test_invalid_or_duplicated_input_never_opens_catalog(self):
        with patch('api.services.places.places.sqlite3.connect') as connect:
            for params in ({}, {'q': 'co'}, {'q': 'x' * 207}, {'q': 'co\x00r'}, {'q': 'cord', 'url': 'https://example.invalid'}):
                self.assertEqual(self.client.get('/api/v1/lugares/', params).status_code, 400)
            self.assertEqual(self.client.get('/api/v1/lugares/?q=cor&q=men').status_code, 400)
            self.assertEqual(self.client.post('/api/v1/lugares/', {'q': 'cor'}).status_code, 405)
            connect.assert_not_called()

    def test_country_region_and_missing_results(self):
        argentina = search_places('Cordoba, Cordoba, ar')
        spain = search_places('Córdoba, Andalusia, ES')
        self.assertEqual((argentina[0]['nombre'], argentina[0]['pais']), ('Córdoba', 'AR'))
        self.assertEqual((spain[0]['nombre'], spain[0]['pais']), ('Córdoba', 'ES'))
        self.assertNotEqual(argentina[0]['id'], spain[0]['id'])
        self.assertTrue(all(row['pais'] == 'AR' for row in argentina))
        self.assertEqual(search_places('Cordoba, Ontario, CA'), [])
        self.assertEqual(search_places('zzzzzznotacity'), [])

    def test_accents_composed_unicode_aliases_and_international_names(self):
        self.assertEqual(search_places('Córdoba, AR'), search_places('Co\u0301rdoba, AR'))
        self.assertEqual(search_places('Cordoba, AR'), search_places('CÓRDOBA, AR'))
        self.assertEqual(search_places('Sao Paulo, BR')[0]['nombre'], 'São Paulo')
        self.assertEqual(search_places('Londres')[0]['nombre'], 'London')
        self.assertEqual(search_places('Tokyo')[0]['pais'], 'JP')
        # A local catalog must support Unicode input, not just ASCII names.
        self.assertTrue(search_places('北京市'))

    def test_real_city_names_rank_before_unrelated_aliases_and_results_are_unique(self):
        rows = search_places('San')
        self.assertEqual(rows[0]['nombre'], 'San')
        self.assertTrue(all(normalize_name(row['nombre']).startswith('san') for row in rows))
        self.assertLessEqual(len(rows), 5)
        self.assertEqual(len({row['id'] for row in rows}), len(rows))
        self.assertEqual(rows, search_places('San'))
        self.assertEqual(search_places('Villa Allende, AR')[0]['nombre'], 'Villa Allende')

    def test_catalog_is_read_only_and_matches_its_manifest(self):
        with sqlite3.connect(catalog_uri(), uri=True) as connection:
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute('DELETE FROM cities')
        manifest = json.loads(CATALOG_PATH.with_suffix('.manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(hashlib.sha256(CATALOG_PATH.read_bytes()).hexdigest(), manifest['catalog_sha256'])
        self.assertGreater(manifest['cities'], 170000)

    def test_catalog_failure_is_safe(self):
        with patch('api.services.places.places.sqlite3.connect', side_effect=sqlite3.DatabaseError('PRIVATE path')):
            response = self.client.get('/api/v1/lugares/', {'q': 'cord'})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('PRIVATE', response.content.decode())

    def test_query_text_cannot_modify_catalog(self):
        self.assertEqual(search_places("'; DROP TABLE cities; --"), [])
        self.assertEqual(search_places('Cordoba, AR')[0]['nombre'], 'Córdoba')
