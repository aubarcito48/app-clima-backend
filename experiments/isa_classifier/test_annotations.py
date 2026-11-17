import io
import json
from pathlib import Path
import tempfile
import unittest
import wave
import subprocess
import sys

import numpy as np

from annotations import read_annotations
from classifier import read_recording
from review_audio import build


class AnnotationTests(unittest.TestCase):
    def test_training_can_require_reviewed_plain_wavs_without_rhubarb(self):
        root = Path(self.folder.name)
        annotations = root / 'labels'
        annotations.mkdir()
        arguments = []
        for index, (split, language) in enumerate([('train', 'es'), ('train', 'en'),
                                                  ('test', 'es'), ('test', 'en')]):
            name = f'{split}-{language}'
            wav = root / f'{name}.wav'
            samples = (.2 * np.sin(2 * np.pi * (index + 1) * 200 * np.arange(16000) / 16000))
            with wave.open(str(wav), 'wb') as writer:
                writer.setnchannels(1)
                writer.setsampwidth(2)
                writer.setframerate(16000)
                writer.writeframes((samples * 32767).astype('<i2').tobytes())
            annotation = {**self.data, 'language': language, 'sha256_pcm': read_recording(wav)[3]}
            (annotations / f'{name}.json').write_text(json.dumps(annotation), encoding='utf8')
            arguments.extend([f'--{split}', f'{language}:{wav}'])
        command = [sys.executable, str(Path(__file__).with_name('run_audio.py')), *arguments,
                   '--annotations-dir', str(annotations), '--require-reviewed',
                   '--output', str(root / 'models')]
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((root / 'models/evaluation.json').read_text())
        for language in ('es', 'en'):
            self.assertEqual(report['languages'][language]['evaluation'][0]['label_source'], 'human-reviewed')
            model = json.loads((root / f'models/audio-{language}.json').read_text())
            self.assertEqual(model['training'][0]['label_source'], 'human-reviewed')
        (annotations / 'test-en.json').unlink()
        rejected = subprocess.run(command, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn('Missing reviewed annotations', rejected.stderr)

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'review.json'
        self.data = {'version': 1, 'media': 'audio', 'source': 'human-reviewed',
                     'language': 'en', 'sha256_pcm': 'test-fingerprint',
                     'mouthCues': [{'start': 0., 'end': .5, 'value': 'X', 'reviewed': True},
                                   {'start': .5, 'end': 1., 'value': 'D', 'reviewed': True}]}

    def read(self):
        self.path.write_text(json.dumps(self.data), encoding='utf8')
        return read_annotations(self.path, 'test-fingerprint', 'en', 1.)

    def test_accepts_complete_review_without_auto_label_metadata(self):
        cues = self.read()
        self.assertEqual([c['value'] for c in cues], ['X', 'D'])
        self.assertNotIn('reviewed', cues[0])

    def test_rejects_wrong_pcm_or_language(self):
        for key, value in [('sha256_pcm', 'other'), ('language', 'es'), ('media', 'image')]:
            original = self.data[key]
            self.data[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.read()
            self.data[key] = original

    def test_rejects_progress_or_unreviewed_intervals(self):
        self.data['source'] = 'in-progress'
        with self.assertRaises(ValueError):
            self.read()
        self.data['source'] = 'human-reviewed'
        self.data['mouthCues'][1]['reviewed'] = False
        with self.assertRaises(ValueError):
            self.read()

    def test_rejects_submillisecond_gaps_and_nonfinite_times(self):
        for start in [.5005, .4995, True, float('nan')]:
            self.data['mouthCues'][1]['start'] = start
            with self.subTest(start=start), self.assertRaises(ValueError):
                self.read()

    def test_rejects_oversized_sidecar(self):
        self.path.write_bytes(b' ' * 262145)
        with self.assertRaises(ValueError):
            read_annotations(self.path, 'test-fingerprint', 'en', 1.)

    def test_editor_accepts_plain_pcm_without_rhubarb_metadata(self):
        wav = Path(self.folder.name) / 'plain.wav'
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(16000)
            writer.writeframes(np.zeros(16000, dtype='<i2').tobytes())
        wav.write_bytes(buffer.getvalue())
        output = Path(self.folder.name) / 'review.html'
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()):
            build(wav, 'en', output)
        html = output.read_text(encoding='utf8')
        self.assertIn(read_recording(wav)[3], html)
        self.assertIn('"reviewed": false', html)
        self.assertNotIn('__ISA_DATA__', html)


if __name__ == '__main__':
    unittest.main()
