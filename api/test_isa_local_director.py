import json
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
import httpx
from jsonschema import Draft202012Validator

from .services.isa_local_director import direct_locally
from .services.isa_director_en import direct_english
from .services.isa_performance import clean_text, read_segments
from .services.recommendations import build_messages, generate_recommendation
from .test_recommendations import CONTRACTS, completion, weather_snapshot
from .test_voice import sample_wav


class LocalDirectionTests(SimpleTestCase):
    def test_degree_typo_does_not_split_temperature_from_its_unit(self):
        text = 'Con 25. °C usá ropa fresca. Llevá agua.'
        plan = direct_locally(text)
        self.assertEqual([s['text'] for s in plan], ['Con 25. °C usá ropa fresca.', 'Llevá agua.'])
        self.assertEqual(' '.join(s['text'] for s in plan), text)

    def test_english_paced_trial_is_opt_in_and_keeps_text_and_spanish_unchanged(self):
        text = 'Wear a light comfortable sweater or tee and a short-sleeve shirt; bring an umbrella.'
        spanish = direct_locally('Usá abrigo. Más tarde evitá salir.')
        baseline = direct_locally(text, language='en')
        paced = direct_english(text, profile='paced-v1')
        self.assertEqual(' '.join(s['text'] for s in paced), text)
        self.assertEqual(read_segments(paced, text), paced)
        self.assertEqual(paced[0]['speed'], .90)
        self.assertEqual(paced[1]['speed'], .96)
        self.assertEqual([s['pause_ms'] for s in paced], [90, 0])
        self.assertEqual(direct_locally(text, language='en'), baseline)
        self.assertEqual(direct_locally('Usá abrigo. Más tarde evitá salir.'), spanish)

    def test_english_paced_profile_respects_sentence_boundaries_and_segment_limit(self):
        text = 'Wear layers at 25.5°C. Take care with wind; bring water. Later add a jacket. Stay dry.'
        plan = direct_english(text, profile='paced-v1')
        self.assertEqual(' '.join(s['text'] for s in plan), text)
        self.assertLessEqual(len(plan), 4)
        self.assertIn('25.5°C.', plan[0]['text'])
        self.assertEqual(plan[0]['pause_ms'], 120)
        self.assertEqual(plan[1]['gesture'], 'isa-down')
        self.assertEqual(plan[-1]['pause_ms'], 0)
        with self.assertRaises(ValueError):
            direct_english(text, profile='unknown')

    def test_tuning_english_does_not_change_approved_spanish_delivery(self):
        spanish = 'Usá abrigo. Más tarde evitá salir.'
        expected = [
            {'text': 'Usá abrigo.', 'gesture': 'isa-awake', 'speed': 1.0, 'energy': 1.0, 'pause_ms': 160},
            {'text': 'Más tarde evitá salir.', 'gesture': 'isa-down', 'speed': .96, 'energy': .96, 'pause_ms': 0},
        ]
        self.assertEqual(direct_locally(spanish), expected)
        with patch('api.services.isa_director_en.DEFAULT_SPEED', .9), \
                patch('api.services.isa_director_en.DEFAULT_PAUSE_MS', 240):
            english = direct_locally('Wear layers. Bring an umbrella.', language='en')
            self.assertEqual(english[0]['speed'], .9)
            self.assertEqual(english[0]['pause_ms'], 240)
            self.assertEqual(direct_locally(spanish), expected)
        self.assertEqual(direct_locally('Wear layers.', language='en')[0]['speed'], 1.0)

    def test_text_is_preserved_and_delivery_is_repeatable_in_both_languages(self):
        cases = [
            ('es', 'Usá una campera liviana con 21.5 °C. Más tarde podés sacarte una capa.'),
            ('es', 'Evitá el calzado abierto; después llevá una campera.'),
            ('es', 'Usá abrigo.\nLlevá paraguas.'),
            ('en', 'Wear a light jacket. Be careful with the wind later.'),
            ('en', 'Wear layers; this evening add a jacket.'),
            ('es', 'Uno. Dos. Tres. Cuatro. Cinco. Seis.'),
        ]
        for language, text in cases:
            with self.subTest(language=language, text=text):
                plan = direct_locally(text, language=language)
                self.assertEqual(' '.join(item['text'] for item in plan), clean_text(text))
                self.assertEqual(plan, direct_locally(text, language=language))
                self.assertEqual(read_segments(plan, text), plan)
                self.assertEqual(plan[-1]['pause_ms'], 0)
                self.assertLessEqual(len(plan), 4)

    def test_neutral_advice_has_no_invented_emotion_and_decimal_stays_together(self):
        plan = direct_locally('Usá abrigo con 10.5 °C.')
        self.assertEqual(plan, [{'text': 'Usá abrigo con 10.5 °C.', 'gesture': 'isa-awake',
                                 'speed': 1.0, 'energy': 1.0, 'pause_ms': 0}])

    def test_caution_precedes_later_and_pauses_exist_only_between_fragments(self):
        plan = direct_locally('Evitá salir más tarde. Después llevá abrigo.')
        self.assertEqual([item['gesture'] for item in plan], ['isa-down', 'isa-right'])
        self.assertEqual([item['pause_ms'] for item in plan], [220, 0])
        self.assertGreaterEqual(plan[0]['speed'], .95)

    def test_invalid_inputs_are_rejected(self):
        for text in ('', '  ', None, 'Texto\x00 inválido', 'Texto\u202e inválido'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                direct_locally(text)
        with self.assertRaises(ValueError):
            direct_locally('Bonjour', language='fr')


@override_settings(ISA_DIRECTOR='local', GROQ_API_KEY='DUMMY', GROQ_MODEL='test-chat-model')
class LocalDirectorIntegrationTests(SimpleTestCase):
    def generate(self, data, *, language='es'):
        requests = []
        def handler(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json=completion(json.dumps(data)))
        result = generate_recommendation(weather_snapshot(), language=language,
                                         transport=httpx.MockTransport(handler))
        self.assertEqual(len(requests), 1)
        return result, requests[0]

    def test_one_call_requests_only_advice_and_returns_the_existing_contract(self):
        text = 'Usá una campera liviana. Más tarde podés sacarte una capa.'
        result, request = self.generate({'texto': text})
        self.assertEqual(result['texto'], text)
        self.assertEqual(result['segmentos'], direct_locally(text))
        prompt = request['messages'][0]['content']
        self.assertNotIn('isa-awake', prompt)
        self.assertNotIn('pause_ms', prompt)
        self.assertIn('No inventes', prompt)
        groq_messages = build_messages(weather_snapshot(), director='groq')
        self.assertEqual(request['messages'][1], groq_messages[1])
        self.assertLess(len(prompt), len(groq_messages[0]['content']))
        schema = json.loads((CONTRACTS / 'response-v1.schema.json').read_text(encoding='utf-8'))
        Draft202012Validator({'$ref': '#/$defs/recomendacion', '$defs': schema['$defs']}).validate(result)

    def test_english_uses_english_rules_and_style(self):
        text = 'Wear layers. Be careful with the wind later.'
        result, request = self.generate({'texto': text}, language='en')
        self.assertEqual(result['segmentos'], direct_locally(text, language='en'))
        self.assertIn('natural English', request['messages'][0]['content'])
        self.assertNotIn('Usá un tono', request['messages'][0]['content'])

    def test_bad_advice_is_rejected_without_a_retry_or_fallback_to_groq_direction(self):
        for data in ({'texto': ''}, {'texto': 'abrigo ' * 41}, {'texto': 'x' * 281},
                     {'texto': 'Llevá\x00 abrigo.'}, {'texto': 'Usá abrigo.', 'segmentos': []},
                     {'texto': ['Usá abrigo.']}, {'other': 'Usá abrigo.'}):
            with self.subTest(data=data):
                result, _ = self.generate(data)
                self.assertEqual(result, {'estado': 'no_disponible', 'texto': None})

    @patch('api.voice_views.synthesize', return_value=sample_wav())
    def test_local_plan_reaches_piper_unchanged(self, synth):
        text = 'Evitá salir sin abrigo. Después usá una campera.'
        result, _ = self.generate({'texto': text})
        response = self.client.post('/api/v1/voz/', json.dumps({
            'texto': text, 'segmentos': result['segmentos'],
        }), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        synth.assert_called_once_with(text, segments=result['segmentos'])

    @override_settings(ISA_DIRECTOR='invalid')
    def test_invalid_mode_does_not_call_the_provider(self):
        with patch('api.services.recommendations.Groq') as provider:
            self.assertEqual(generate_recommendation(weather_snapshot()),
                             {'estado': 'no_disponible', 'texto': None})
        provider.assert_not_called()
