import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

import numpy as np

from build_short_plan import make_plan
from narration import app_text, app_performance, advice_spans, PHRASES
from train_next import evaluate
from train_short import core_mask
import temporal


class NarrationTests(unittest.TestCase):
    def test_per_window_training_focus_is_bounded_and_validated(self):
        row = {'features': np.array([[0.], [0.], [1.], [1.]]),
               'labels': np.array(['X', 'X', 'B', 'B']), 'loss_weights': np.array([.25, .25, 1., 1.])}
        model = temporal.fit([row], balance=0, weight_cap=4)
        self.assertTrue(model['per_window_focus'])
        self.assertAlmostEqual(model['weight_range'][1] / model['weight_range'][0], 4)
        for invalid in ([1], [1, 1, -1, 1], [1, 1, float('nan'), 1]):
            with self.assertRaises(ValueError):
                temporal.fit([{**row, 'loss_weights': invalid}])

    def test_all_48_samples_use_short_advice_and_exact_app_phrases(self):
        rows = make_plan()['recordings']
        self.assertEqual(len(rows), 48)
        for row in rows:
            greeting, farewell = PHRASES[row['language']]
            self.assertTrue(row['text'].startswith(greeting + '\n'))
            self.assertTrue(row['text'].endswith('\n' + farewell))
            self.assertEqual(row['text'], app_text(row['advice'], row['language']))
            self.assertLessEqual(len(row['advice'].split()), 40)
            self.assertLessEqual(len(row['advice']), 280)

    def test_greeting_and_farewell_are_neutral_with_app_pauses(self):
        def director(text, *, language):
            return [{'text': text, 'gesture': 'isa-right', 'speed': 1.1, 'energy': 1, 'pause_ms': 100}]
        text, segments = app_performance('Take a coat.', 'en', director)
        self.assertEqual(text, 'Hello, explorer!\nTake a coat.\nSee you later, explorer!')
        self.assertEqual(segments[0]['pause_ms'], 160)
        self.assertEqual(segments[-1]['pause_ms'], 0)
        self.assertEqual(segments[1]['gesture'], 'isa-right')

    def test_phrases_still_match_current_frontend_source(self):
        frontend = Path(__file__).resolve().parents[3] / 'app-clima/src/app/service/isabel-voice.ts'
        if not frontend.is_file():
            self.skipTest('Frontend checkout not available')
        source = frontend.read_text(encoding='utf8')
        for phrases in PHRASES.values():
            for phrase in phrases:
                self.assertIn(phrase, source)
        self.assertIn('pause_ms: 160', source)
        self.assertIn('pause_ms: 0', source)

    def test_double_greetings_and_long_advice_rejected(self):
        for advice in ('¡Buenas, explorador! Usá abrigo.', 'word ' * 41, 'x' * 281):
            with self.assertRaises(ValueError):
                app_text(advice, 'es')

    def test_spans_come_from_actual_performance_and_exclude_bookends(self):
        rows = [{'from': 0, 'speech_end': .2, 'until': .3},
                {'from': .3, 'speech_end': .7, 'until': .8},
                {'from': .8, 'speech_end': 1., 'until': 1.}]
        payload = json.dumps(rows).encode()
        audio = b'RIFF\0\0\0\0WAVEisac' + struct.pack('<I', len(payload)) + payload
        audio += b'\0' * (len(payload) % 2)
        self.assertEqual(advice_spans(audio, 1.), [[.3, .7]])
        rows[1]['from'] = .31
        payload = json.dumps(rows).encode()
        audio = b'RIFF\0\0\0\0WAVEisac' + struct.pack('<I', len(payload)) + payload + b'\0' * (len(payload) % 2)
        with self.assertRaises(ValueError):
            advice_spans(audio, 1.)

    def test_memorizing_greetings_does_not_raise_advice_metrics(self):
        labels = np.array(['X'] * 20 + ['B'] * 60 + ['X'] * 20)
        predicted = np.array(['X'] * 20 + ['C'] * 60 + ['X'] * 20)
        row = {'file': 'synthetic.wav', 'labels': labels, 'features': np.zeros((100, 2)),
               'hop': .01, 'duration': 1., 'advice_spans': [[.2, .8]]}
        row['advice_mask'] = core_mask(row)
        with patch('train_next.temporal.predict', return_value=predicted):
            full, _ = evaluate([row], {})
            core, _ = evaluate([row], {}, advice_only=True)
        self.assertAlmostEqual(full['mean_recording_agreement'], .4)
        self.assertEqual(core['mean_recording_agreement'], 0)
        self.assertEqual(core['pooled']['macro_f1'], 0)


if __name__ == '__main__':
    unittest.main()
