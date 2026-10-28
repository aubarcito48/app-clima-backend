import io
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock, patch
import wave

from django.test import SimpleTestCase, override_settings

from .services.voice import VoiceBusy, VoiceUnavailable, _gate, synthesize
from .services.voice_chunks import MAX_CHUNK_PHONEMES, prepare_voice_chunks, split_voice_phonemes
from .services.voice_memory import memory_snapshot, trace_voice_memory


def sample_wav():
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(22050)
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
            self.assertEqual(audio.getframerate(), 22050)
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
    def test_short_numeric_text_is_split_after_pronunciation_expands_it(self):
        tokenizer = Mock()
        pronunciation = 'nwˈeβe pˈunto noβˈenta i θˈinko ɡɾˈaðos θˈelsjus '
        tokenizer.phonemize.return_value = [list(pronunciation * 2)]
        chunks = prepare_voice_chunks(tokenizer, '9.95 °C')
        tokenizer.phonemize.assert_called_once_with('9.95 °C')
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= MAX_CHUNK_PHONEMES for chunk in chunks))
        self.assertEqual(' '.join(''.join(chunk) for chunk in chunks), (pronunciation * 2).strip())

    def test_expanded_pronunciation_is_bounded_without_losing_stress_or_sounds(self):
        text = ('oɪ en kˈoɾðoβa ˈaθe ðjˈeθ ɡɾˈaðos. ʝˈeβa ˈuna tʃakˈeta lixˈeɾa; ' * 8)
        chunks = list(split_voice_phonemes(text))
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(0 < len(chunk) <= MAX_CHUNK_PHONEMES for chunk in chunks))
        self.assertEqual(' '.join(''.join(chunk) for chunk in chunks), ' '.join(text.split()))

    def test_unbroken_input_is_also_bounded_and_never_truncated(self):
        text = 'á' * 600
        chunks = list(split_voice_phonemes(text))
        self.assertEqual(''.join(''.join(chunk) for chunk in chunks), text)
        self.assertTrue(all(len(chunk) <= MAX_CHUNK_PHONEMES for chunk in chunks))

    def test_short_text_and_whitespace(self):
        self.assertEqual(list(split_voice_phonemes('  ˈola ˈisa.  ')), [list('ˈola ˈisa.')])
        self.assertEqual(list(split_voice_phonemes('   ')), [])

    def test_compound_phoneme_symbols_are_never_split_or_lost(self):
        phonemes = ['a̪'] * (MAX_CHUNK_PHONEMES + 5)
        chunks = list(split_voice_phonemes(phonemes))
        self.assertEqual([symbol for chunk in chunks for symbol in chunk], phonemes)


class VoiceMemoryTests(SimpleTestCase):
    @patch('api.services.voice_memory._read')
    def test_reports_process_and_container_separately(self, read):
        contents = {
            '/proc/self/status': 'Name:\tpython\nVmRSS:\t102400 kB\nVmHWM:\t153600 kB\n',
            '/sys/fs/cgroup/memory.current': str(450 * 1048576),
            '/sys/fs/cgroup/memory.max': str(512 * 1048576),
            '/sys/fs/cgroup/memory.stat': f'anon {300 * 1048576}\nfile {150 * 1048576}\n',
        }
        read.side_effect = lambda path: contents.get(path, '')
        self.assertEqual(memory_snapshot(), {
            'rss_mib': 100.0, 'peak_rss_mib': 150.0, 'cgroup_current_mib': 450.0,
            'cgroup_limit_mib': 512.0, 'cgroup_anon_mib': 300.0, 'cgroup_file_mib': 150.0,
        })

    @patch('api.services.voice_memory._read', return_value='')
    def test_absent_counters_are_not_reported_as_zero(self, read):
        self.assertEqual(memory_snapshot(), {})

    @patch('api.services.voice_memory.sys.platform', 'linux')
    @patch('api.services.voice_memory.memory_snapshot', return_value={'rss_mib': 100.0})
    def test_diagnostics_never_accept_arbitrary_text(self, snapshot):
        output = io.StringIO()
        with patch('api.services.voice_memory.sys.__stderr__', output):
            trace_voice_memory('PRIVATE-TEXT')
            trace_voice_memory('model_ready', 'PRIVATE-TEXT', tokens='PRIVATE-TEXT')
        self.assertEqual(json.loads(output.getvalue()), {
            'event': 'isa_memory', 'engine': 'piper', 'stage': 'model_ready', 'rss_mib': 100.0,
        })
