from unittest.mock import patch

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
        self.assertEqual(spanish[1], english[1])
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
