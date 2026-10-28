import io
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import patch
import wave

from django.test import SimpleTestCase, override_settings

from .services.voice import VoiceBusy, VoiceUnavailable, _gate, synthesize
from .services.voice_chunks import MAX_CHUNK_CHARACTERS, split_voice_text


def sample_wav():
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(24000)
        output.writeframes(b'\x00\x00' * 240)
    return buffer.getvalue()


class VoiceEndpointTests(SimpleTestCase):
    def post(self, payload):
        return self.client.post('/api/v1/voz/', json.dumps(payload), content_type='application/json')

    @patch('api.voice_views.synthesize', return_value=sample_wav())
    def test_exact_groq_text_becomes_non_cached_wav(self, synth):
        text = 'Llevá abrigo.\nEn Córdoba refresca.'
        response = self.post({'texto': text})
        synth.assert_called_once_with(text)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'audio/wav')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        with wave.open(io.BytesIO(response.content)) as audio:
            self.assertEqual(audio.getframerate(), 24000)
        self.assertEqual(response.content, sample_wav())

    @patch('api.voice_views.synthesize')
    def test_invalid_inputs_never_start_a_worker(self, synth):
        for payload in [None, [], 'texto', {}, {'texto': ''}, {'texto': ' '}, {'texto': 4},
                        {'texto': 'x' * 601}, {'texto': 'hola\x00'}, {'texto': 'hola', 'voz': 'otra'}]:
            with self.subTest(payload=payload):
                self.assertEqual(self.post(payload).status_code, 400)
        self.assertEqual(self.client.post('/api/v1/voz/', '{', content_type='application/json').status_code, 400)
        self.assertEqual(self.client.post('/api/v1/voz/', 'x' * 8193, content_type='application/json').status_code, 413)
        synth.assert_not_called()

    def test_method_and_content_type(self):
        response = self.client.get('/api/v1/voz/')
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response['Allow'], 'POST')
        self.assertEqual(self.client.post('/api/v1/voz/', {'texto': 'Hola'}).status_code, 415)

    @patch('api.voice_views.synthesize', side_effect=VoiceUnavailable('PRIVATE-PATH'))
    def test_failure_is_public_and_does_not_expose_worker_details(self, synth):
        response = self.post({'texto': 'Hola'})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['codigo'], 'VOZ_NO_DISPONIBLE')
        self.assertNotIn('PRIVATE', response.content.decode())
        self.assertIn('no-store', response['Cache-Control'])

    @patch('api.voice_views.synthesize', side_effect=VoiceBusy())
    def test_busy_has_retry_after(self, synth):
        response = self.post({'texto': 'Hola'})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response['Retry-After'], '5')

    def test_json_post_preflight_for_angular(self):
        response = self.client.options('/api/v1/voz/', HTTP_ORIGIN='http://localhost:4200',
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST', HTTP_ACCESS_CONTROL_REQUEST_HEADERS='content-type')
        self.assertEqual(response['Access-Control-Allow-Origin'], 'http://localhost:4200')
        self.assertIn('POST', response['Access-Control-Allow-Methods'])


@override_settings(ISA_MODEL_DIR=Path('models/test-only'))
class VoiceWorkerTests(SimpleTestCase):
    @patch('api.services.voice.subprocess.run')
    def test_bounded_worker_receives_text_via_stdin_without_shell(self, run):
        run.return_value = SimpleNamespace(returncode=0, stdout=sample_wav())
        self.assertEqual(synthesize('Llevá abrigo.'), sample_wav())
        args, kwargs = run.call_args
        self.assertNotIn('Llevá abrigo.', args[0])
        self.assertEqual(kwargs['input'], 'Llevá abrigo.'.encode())
        self.assertEqual(kwargs['timeout'], 45)
        self.assertNotIn('shell', kwargs)

    @patch('api.services.voice.subprocess.run')
    def test_timeout_and_invalid_audio_release_the_gate(self, run):
        for failure in [subprocess.TimeoutExpired('worker', 45), OSError('private')]:
            run.side_effect = failure
            with self.assertRaises(VoiceUnavailable):
                synthesize('Hola')
            self.assertFalse(_gate.locked())
        run.side_effect = None
        for result in [SimpleNamespace(returncode=1, stdout=sample_wav()),
                       SimpleNamespace(returncode=0, stdout=b'PRIVATE-LOG'),
                       SimpleNamespace(returncode=0, stdout=b'x' * 4_320_045)]:
            run.return_value = result
            with self.assertRaises(VoiceUnavailable):
                synthesize('Hola')
            self.assertFalse(_gate.locked())

    @patch('api.services.voice.subprocess.run')
    def test_concurrent_requests_do_not_queue_unbounded_workers(self, run):
        _gate.acquire()
        try:
            with self.assertRaises(VoiceBusy):
                synthesize('Hola')
            run.assert_not_called()
        finally:
            _gate.release()


class VoiceChunkTests(SimpleTestCase):
    def test_preserves_all_words_accents_numbers_and_decimals_in_long_advice(self):
        text = ('En Córdoba hacen 10.5 °C y la humedad es del 94 %. '
                'Llevá una campera ligera; por la tarde podés quitarte una capa. ' * 5)[:600]
        chunks = list(split_voice_text(text))
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(0 < len(chunk) <= MAX_CHUNK_CHARACTERS for chunk in chunks))
        self.assertEqual(' '.join(chunks), ' '.join(text.split()))
        self.assertTrue(any('10.5' in chunk for chunk in chunks))

    def test_unbroken_input_is_also_bounded_and_never_truncated(self):
        text = 'á' * 600
        chunks = list(split_voice_text(text))
        self.assertEqual(''.join(chunks), text)
        self.assertTrue(all(len(chunk) <= MAX_CHUNK_CHARACTERS for chunk in chunks))

    def test_short_text_and_whitespace(self):
        self.assertEqual(list(split_voice_text('  Hola, Isa.  ')), ['Hola, Isa.'])
        self.assertEqual(list(split_voice_text('   ')), [])
