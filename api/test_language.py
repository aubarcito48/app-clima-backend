from unittest.mock import patch
import json

from django.test import SimpleTestCase

from .services.climate import query_climate
from .services.recommendations import build_messages
from .services.weather import OpenWeatherMeteorology
from .test_recommendations import weather_snapshot
from .test_weather import LOCATION, CURRENT
from .validation import ClimateQueryForm


class LanguageTests(SimpleTestCase):
    def test_city_and_coordinate_queries_accept_only_supported_languages(self):
        for query in ({'ciudad': 'Córdoba'}, {'latitud': '-31.42', 'longitud': '-64.18'}):
            for language in ('es', 'en'):
                with self.subTest(query=query, language=language):
                    form = ClimateQueryForm({**query, 'idioma': language})
                    self.assertTrue(form.is_valid(), form.errors)
                    self.assertEqual(form.query().idioma, language)
            self.assertFalse(ClimateQueryForm({**query, 'idioma': 'fr'}).is_valid())
            self.assertEqual(ClimateQueryForm(query).query().idioma, 'es')

    def test_english_weather_requests_use_provider_language(self):
        with patch('api.services.weather.request_json', return_value=CURRENT) as request:
            OpenWeatherMeteorology('en').current(LOCATION)
        self.assertEqual(request.call_args.args[1]['lang'], 'en')

    def test_english_prompt_keeps_the_same_measurements_and_safety_instructions(self):
        snapshot = weather_snapshot()
        spanish = build_messages(snapshot)
        english = build_messages(snapshot, language='en')
        spanish_data = json.loads(spanish[1]['content'])
        english_data = json.loads(english[1]['content'])
        # Only the readable clock wording changes; dates and measurements agree.
        for es_row, en_row in zip(
            [spanish_data['actual'], *spanish_data['pronostico']['intervalos']],
            [english_data['actual'], *english_data['pronostico']['intervalos']],
        ):
            es_time = es_row.pop('momento_local')
            en_time = en_row.pop('momento_local')
            self.assertEqual(es_time.split(',')[0], en_time.split(',')[0])
        self.assertEqual(spanish_data, english_data)
        self.assertIn('consejo breve en inglés', english[0]['content'])
        self.assertNotIn('en español', english[0]['content'])
        self.assertIn('No inventes', english[0]['content'])
        with self.assertRaises(ValueError):
            build_messages(snapshot, language='fr')

    def test_language_is_passed_through_the_full_climate_query(self):
        snapshot = weather_snapshot()
        query = ClimateQueryForm({'ciudad': 'Córdoba', 'idioma': 'en'}).query()
        with patch('api.services.climate.resolve_location', return_value=LOCATION), \
             patch('api.services.climate.fetch_weather', return_value=snapshot) as weather, \
             patch('api.services.climate.generate_recommendation', return_value={'estado': 'no_disponible', 'texto': None}) as advice:
            result = query_climate(query)
        weather.assert_called_once_with(LOCATION, language='en')
        advice.assert_called_once_with(snapshot, language='en')
        self.assertEqual(result['actual'], snapshot.actual)
