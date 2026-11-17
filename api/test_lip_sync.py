import io
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch
import wave
import zipfile

from django.test import SimpleTestCase, override_settings

from .services.lip_sync import add_lip_sync, append_mouth_cues, read_mouth_cues
from .services.voice import VoiceBusy, _gate, synthesize
from .test_voice import sample_wav


class MouthCueTests(SimpleTestCase):
    def test_audio_relative_cues_preserve_pcm_and_existing_segment_metadata(self):
        from .services.isa_performance import append_timeline
        original = append_timeline(sample_wav(), [{'from': 0, 'speech_end': .01, 'until': .01, 'gesture': 'isa-awake'}])
        cues = read_mouth_cues({'metadata': {'soundFile': 'PRIVATE'}, 'mouthCues': [
            {'start': 0, 'end': .01, 'value': 'X'}]}, 240 / 22050)
        result = append_mouth_cues(original, cues)
        self.assertIn(b'isac', result)
        self.assertIn(b'isav', result)
        self.assertNotIn(b'PRIVATE', result)
        self.assertEqual(int.from_bytes(result[4:8], 'little'), len(result) - 8)
        with wave.open(io.BytesIO(result)) as audio:
            self.assertEqual(audio.readframes(240), sample_wav()[44:])

    def test_unknown_shapes_nonfinite_times_gaps_overlaps_and_truncation_are_rejected(self):
        cases = [[], [{'start': 0, 'end': 1, 'value': 'smile'}],
                 [{'start': True, 'end': 1, 'value': 'A'}],
                 [{'start': 0, 'end': float('nan'), 'value': 'A'}],
                 [{'start': 0, 'end': 2, 'value': 'A'}],
                 [{'start': .5, 'end': 1, 'value': 'A'}],
                 [{'start': 0, 'end': .2, 'value': 'A'}],
                 [{'start': 0, 'end': .7, 'value': 'A'}, {'start': .2, 'end': 1, 'value': 'X'}]]
        for rows in cases:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                read_mouth_cues({'mouthCues': rows}, 1)

    def test_real_recognizer_centisecond_rounding_is_accepted(self):
        rows = [{'start': 0, 'end': .5, 'value': 'A'}, {'start': .5, 'end': 1, 'value': 'X'}]
        self.assertEqual(read_mouth_cues({'mouthCues': rows}, 1.007), rows)


class OptionalRecognizerTests(SimpleTestCase):
    def run_probe(self, *, data=None, status=0, timeout=False):
        original = sample_wav()
        process = Mock()
        process.returncode = status
        process.poll.return_value = status
        process.wait.side_effect = [subprocess.TimeoutExpired('rhubarb', 1), 0] if timeout else None
        with tempfile.TemporaryDirectory() as folder:
            binary = Path(folder) / 'rhubarb'
            binary.touch()
            def launch(args, **kwargs):
                output = Path(args[args.index('-o') + 1])
                output.write_text(json.dumps(data if data is not None else {
                    'mouthCues': [{'start': 0, 'end': .01, 'value': 'X'}],
                    'metadata': {'soundFile': 'PRIVATE'},
                }), encoding='utf8')
                return process
            with patch('api.services.lip_sync.subprocess.Popen', side_effect=launch) as popen:
                result = add_lip_sync(original, binary, timeout=1)
        return original, result, process, popen

    def test_success_uses_local_phonetic_recognizer_one_thread_and_adds_optional_chunk(self):
        original, result, _, popen = self.run_probe()
        self.assertGreater(len(result), len(original))
        args = popen.call_args.args[0]
        self.assertIn('phonetic', args)
        self.assertEqual(args[args.index('--threads') + 1], '1')
        self.assertNotIn(b'PRIVATE', result)
        self.assertIn(b'isav', result)

    def test_invalid_json_or_exit_failure_keeps_original_audio(self):
        for options in ({'status': 1}, {'data': {'mouthCues': []}}, {'data': {'mouthCues': 'bad'}}):
            with self.subTest(options=options):
                original, result, _, _ = self.run_probe(**options)
                self.assertEqual(result, original)

    def test_timeout_kills_and_reaps_recognizer_then_keeps_audio(self):
        original, result, process, _ = self.run_probe(timeout=True)
        self.assertEqual(result, original)
        process.kill.assert_called_once()
        self.assertEqual(process.wait.call_count, 2)

    @patch('api.services.lip_sync.subprocess.Popen')
    def test_missing_binary_or_exhausted_budget_never_starts_a_process(self, popen):
        original = sample_wav()
        self.assertEqual(add_lip_sync(original, Path('missing/test/rhubarb'), timeout=1), original)
        self.assertEqual(add_lip_sync(original, Path('missing/test/rhubarb'), timeout=0), original)
        popen.assert_not_called()


@override_settings(ISA_LIP_SYNC='rhubarb', ISA_RHUBARB_PATH=Path('test/rhubarb'), ISA_RHUBARB_TIMEOUT_SECONDS=60)
class VoiceLipIntegrationTests(SimpleTestCase):
    @patch('api.services.voice.classify_after_synthesis')
    @patch('api.services.voice.subprocess.run')
    def test_recognizer_runs_only_after_piper_exits_with_gate_still_locked(self, run, lip):
        run.return_value = SimpleNamespace(returncode=0, stdout=sample_wav())
        def recognize(audio, language):
            self.assertEqual(run.call_count, 1)
            self.assertTrue(_gate.locked())
            with self.assertRaises(VoiceBusy):
                synthesize('Second request')
            self.assertEqual(language, 'es')
            return audio
        lip.side_effect = recognize
        self.assertEqual(synthesize('Usá abrigo.'), sample_wav())
        self.assertFalse(_gate.locked())

    @override_settings(ISA_LIP_SYNC='off')
    @patch('api.services.voice.classify_after_synthesis')
    @patch('api.services.voice.subprocess.run')
    def test_off_retains_previous_path(self, run, lip):
        run.return_value = SimpleNamespace(returncode=0, stdout=sample_wav())
        self.assertEqual(synthesize('Usá abrigo.'), sample_wav())
        lip.assert_not_called()

    @override_settings(ISA_LIP_SYNC='own')
    @patch('api.services.voice.classify_after_synthesis', side_effect=lambda audio, *args, **kwargs: audio)
    @patch('api.services.voice.subprocess.run')
    def test_recognizer_has_its_own_configured_budget_after_piper(self, run, lip):
        run.return_value = SimpleNamespace(returncode=0, stdout=sample_wav())
        synthesize('Usá abrigo.')
        self.assertEqual(lip.call_args.args[1], 'es')
        self.assertIn('--own-lip-sync', run.call_args.args[0])


class RuntimeInstallerTests(SimpleTestCase):
    def install_fixture(self, *, corrupt=False, traversal=False):
        from scripts import install_rhubarb as installer
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            archive, target = folder / 'runtime.zip', folder / 'runtime'
            prefix = 'Rhubarb-Lip-Sync-1.14.0-Linux/'
            with zipfile.ZipFile(archive, 'w') as package:
                for name in ('rhubarb', 'res/model.bin', 'LICENSE.md', 'extras/demo.wav', 'tests/test.wav'):
                    package.writestr(prefix + name, 'fixture')
                if traversal:
                    package.writestr(prefix + 'res/../../escape', 'fixture')
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            with (patch.object(installer.platform, 'system', return_value='Linux'),
                  patch.object(installer.platform, 'machine', return_value='x86_64'),
                  patch.object(installer, 'ARCHIVES', {'Linux': (archive.stat().st_size, '0' * 64 if corrupt else digest)})):
                if corrupt or traversal:
                    with self.assertRaises(RuntimeError):
                        installer.install(target=target, from_zip=archive)
                    self.assertFalse((folder / 'escape').exists())
                else:
                    installer.install(target=target, from_zip=archive)
                    self.assertTrue((target / 'rhubarb').is_file())
                    self.assertTrue((target / 'LICENSE.md').is_file())
                    self.assertFalse((target / 'extras').exists())
                    self.assertFalse((target / 'tests').exists())
                    installer.install(target=target, from_zip=archive)

    def test_only_verified_runtime_resources_and_license_are_installed(self):
        self.install_fixture()

    def test_checksum_mismatch_stops_installation(self):
        self.install_fixture(corrupt=True)

    def test_resource_path_cannot_escape_the_installation(self):
        self.install_fixture(traversal=True)
