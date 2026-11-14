from copy import deepcopy
import io
import json
from types import SimpleNamespace
from unittest.mock import patch
import wave

from django.test import SimpleTestCase, override_settings
import httpx
from jsonschema import Draft202012Validator

from .services.isa_performance import append_timeline
from .services.recommendations import generate_recommendation
from .services.voice import synthesize
from .test_recommendations import CONTRACTS, completion, weather_snapshot
from .test_voice import sample_wav


def segment(text='Llevá abrigo.', gesture='isa-down', **options):
    return {'text': text, 'gesture': gesture, 'speed': .9, 'energy': .85, 'pause_ms': 300, **options}


@override_settings(GROQ_API_KEY='DUMMY', GROQ_MODEL='test-chat-model')
class IsaDirectionTests(SimpleTestCase):
    def generate(self, data):
        return generate_recommendation(weather_snapshot(), transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=completion(json.dumps(data)))))

    def test_groq_returns_exact_advice_and_only_isa_gestures(self):
        parts = [segment(), segment('Después podés quitarte una capa.', 'isa-right', speed=1.1)]
        text = ' '.join(part['text'] for part in parts)
        result = self.generate({'texto': text, 'segmentos': parts})
        self.assertEqual(result, {'estado': 'disponible', 'texto': text, 'segmentos': parts})
        schema = json.loads((CONTRACTS / 'response-v1.schema.json').read_text(encoding='utf-8'))
        Draft202012Validator({'$ref': '#/$defs/recomendacion', '$defs': schema['$defs']}).validate(result)

    def test_invalid_gestures_delivery_and_rewritten_fragments_never_escape_validation(self):
        for options in ({'gesture': 'happy'}, {'gesture': 'isa-sleep'}, {'speed': True},
                        {'speed': float('inf')}, {'energy': .1}, {'pause_ms': 601},
                        {'pause_ms': 1.5}, {'text': 'Texto diferente.'}, {'text': 'Llevá\x00 abrigo.'}):
            with self.subTest(options=options):
                data = {'texto': 'Llevá abrigo.', 'segmentos': [segment(**options)]}
                self.assertEqual(self.generate(data), {'estado': 'no_disponible', 'texto': None})

    def test_text_limits_apply_to_advice_not_json_metadata(self):
        text = ' '.join(['abrigo'] * 40) + '.'
        data = {'texto': text, 'segmentos': [segment(text)]}
        self.assertEqual(self.generate(data)['texto'], text)
        data['texto'] += 'x'
        data['segmentos'][0]['text'] += 'x'
        self.assertEqual(self.generate(data)['estado'], 'no_disponible')

    @patch('api.voice_views.synthesize', return_value=sample_wav())
    def test_voice_endpoint_passes_validated_plan_and_rejects_text_mismatch(self, synth):
        plan = [segment()]
        response = self.client.post('/api/v1/voz/', json.dumps({'texto': 'Llevá abrigo.', 'segmentos': plan}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        synth.assert_called_once_with('Llevá abrigo.', segments=plan)
        invalid = deepcopy(plan)
        invalid[0]['text'] = 'Otro texto'
        self.assertEqual(self.client.post('/api/v1/voz/', json.dumps({'texto': 'Llevá abrigo.', 'segmentos': invalid}), content_type='application/json').status_code, 400)
        self.assertEqual(synth.call_count, 1)

    @patch('api.services.voice.subprocess.run')
    def test_one_bounded_worker_receives_the_complete_plan(self, run):
        run.return_value = SimpleNamespace(returncode=0, stdout=sample_wav())
        synthesize('Llevá abrigo.', segments=[segment()])
        args, options = run.call_args
        self.assertEqual(args[0][-1], '--performance')
        self.assertEqual(json.loads(options['input']), {'texto': 'Llevá abrigo.', 'segmentos': [segment()]})
        self.assertEqual(options['timeout'], 45)

    def test_timeline_chunk_preserves_standard_wav_audio(self):
        original = sample_wav()
        cues = [{'from': 0, 'speech_end': .01, 'until': .01, 'gesture': 'isa-down'}]
        audio = append_timeline(original, cues)
        self.assertEqual(int.from_bytes(audio[4:8], 'little'), len(audio) - 8)
        with wave.open(io.BytesIO(audio)) as wav:
            self.assertEqual(wav.getnframes(), 240)
            self.assertEqual(wav.readframes(240), original[44:])
        offset = len(original)
        self.assertEqual(audio[offset:offset + 4], b'isac')
        size = int.from_bytes(audio[offset + 4:offset + 8], 'little')
        self.assertEqual(json.loads(audio[offset + 8:offset + 8 + size]), cues)
