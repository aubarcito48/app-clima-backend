"""Independent synthetic checks: no network, Piper, Rhubarb or model downloads."""

import io
import json
from pathlib import Path
import tempfile
import unittest
import wave
from contextlib import redirect_stdout

import numpy as np

from classifier import audio_features, classify, fit, labels_at, read_recording, smooth, timeline
from review_images import build
from PIL import Image


class ClassifierTests(unittest.TestCase):
    def test_image_review_uses_atlas_indices_not_trimmed_video_indices(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'src/app/shared/isabel'
            source.mkdir(parents=True)
            (root / 'public').mkdir()
            atlas = Image.new('RGB', (640, 320), 'white')
            atlas.paste('black', (320, 0, 640, 320))
            atlas.save(root / 'public/atlas.webp')
            (source / 'isa-speech-manifest-en.json').write_text(json.dumps({
                'sourceFrames': [12, 13], 'width': 320, 'height': 320, 'columns': 2,
                'pages': [{'first': 0, 'count': 2, 'image': 'atlas.webp'}]}))
            (source / 'isa-speech-selection-en.json').write_text(json.dumps({
                'candidates': [0, 1], 'labels': ['X', 'D']}))
            output = root / 'output'
            with redirect_stdout(io.StringIO()):
                build(root, 'en', output, [120, 111, 190, 151])
            html = (output / 'review-en.html').read_text(encoding='utf8')
            self.assertIn('"sourceFrame": 12', html)
            self.assertIn('"index": 0', html)
            model = json.loads((output / 'image-en.json').read_text())
            self.assertEqual(model['classes'], ['D', 'X'])
            reviewed = root / 'labels.json'
            reviewed.write_text(json.dumps({'version': 1, 'language': 'es',
                'roi': [120, 111, 190, 151], 'source': 'human-reviewed', 'labels': []}))
            with self.assertRaises(ValueError):
                build(root, 'en', output, [120, 111, 190, 151], reviewed)

    def test_audio_features_cover_partial_last_hop_and_are_finite(self):
        samples = np.zeros(22051)
        features, times, hop = audio_features(samples, 22050)
        self.assertEqual(len(features), len(times))
        self.assertTrue(np.isfinite(features).all())
        self.assertLess(times[-1], len(samples) / 22050)
        cues = timeline(np.full(len(times), 'X'), hop, len(samples) / 22050)
        self.assertEqual(cues[0]['start'], 0)
        self.assertAlmostEqual(cues[-1]['end'], len(samples) / 22050, places=6)

    def test_spectral_features_distinguish_low_and_high_tones(self):
        time = np.arange(16000) / 16000
        low, _, _ = audio_features(.5 * np.sin(2 * np.pi * 200 * time), 16000)
        high, _, _ = audio_features(.5 * np.sin(2 * np.pi * 3000 * time), 16000)
        self.assertGreater(np.linalg.norm(low.mean(axis=0) - high.mean(axis=0)), 1)

    def test_fit_and_classify_separate_clusters_without_reference_at_inference(self):
        model = fit([[0, 0], [.1, 0], [5, 5], [5, 5.1]], ['X', 'X', 'D', 'D'])
        labels, margins = classify(json.loads(json.dumps(model)), [[0, .1], [5.1, 5]])
        self.assertEqual(labels.tolist(), ['X', 'D'])
        self.assertTrue((margins > 0).all())

    def test_invalid_training_values_are_rejected(self):
        for features, labels in (([[float('nan')]], ['X']), ([[1]], ['Z']), ([], [])):
            with self.assertRaises(ValueError):
                fit(features, labels)

    def test_reference_boundaries_use_next_cue_and_cover_audio(self):
        cues = [{'start': 0, 'end': .5, 'value': 'X'}, {'start': .5, 'end': 1, 'value': 'D'}]
        self.assertEqual(labels_at(cues, np.array([.49, .5, .99]), 1).tolist(), ['X', 'D', 'D'])
        with self.assertRaises(ValueError):
            labels_at(cues, np.array([.1]), 2)
        cues[1]['start'] = .8
        with self.assertRaises(ValueError):
            labels_at(cues, np.array([.1]), 1)

    def test_smoothing_and_timeline_preserve_closure_and_contiguity(self):
        labels = smooth(np.array(list('XXDXXDDD')))
        cues = timeline(labels, .01, .075)
        self.assertEqual([c['value'] for c in cues], ['X', 'D'])
        self.assertEqual(cues[0]['end'], cues[1]['start'])
        self.assertEqual(cues[-1]['end'], .075)

    def test_pcm_identity_ignores_container_metadata(self):
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b'\0\0' * 1600)
        original = buffer.getvalue()
        altered = original + b'JUNK' + (2).to_bytes(4, 'little') + b'AB'
        altered = altered[:4] + (len(altered) - 8).to_bytes(4, 'little') + altered[8:]
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder) / 'a.wav', Path(folder) / 'b.wav'
            a.write_bytes(original)
            b.write_bytes(altered)
            self.assertEqual(read_recording(a)[3], read_recording(b)[3])
            b.write_bytes(altered[:-1])
            with self.assertRaises(ValueError):
                read_recording(b)


if __name__ == '__main__':
    unittest.main()
