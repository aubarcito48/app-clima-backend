import copy
import json
from pathlib import Path
import unittest

import numpy as np

from generate_corpus import validate_plan
import temporal


class TemporalTests(unittest.TestCase):
    def test_context_clamps_edges_instead_of_wrapping_to_other_recordings(self):
        result = temporal.context([[10.], [20.], [30.]])
        self.assertEqual(result[0].tolist(), [10., 10., 10., 30., 30.])
        self.assertEqual(result[-1].tolist(), [10., 10., 30., 30., 30.])
        other = temporal.context([[100.]])
        self.assertEqual(other[0].tolist(), [100.] * 5)

    def test_regularized_training_roundtrip_and_sequence_decode(self):
        rng = np.random.default_rng(19)
        training = [
            {'features': rng.normal(-3, .1, (30, 2)), 'labels': np.full(30, 'X')},
            {'features': rng.normal(3, .1, (30, 2)), 'labels': np.full(30, 'D')},
        ]
        model = temporal.fit(training)
        # Independent feature rows; no reference labels are passed to inference.
        query = np.concatenate([np.full((20, 2), -3.), np.full((20, 2), 3.)])
        model['transition_strength'] = .05
        predicted = temporal.predict(json.loads(json.dumps(model)), query)
        self.assertEqual(predicted[5], 'X')
        self.assertEqual(predicted[-5], 'D')
        self.assertEqual(len(predicted), len(query))

    def test_separate_recordings_do_not_add_cross_recording_transitions(self):
        model = temporal.fit([
            {'features': np.zeros((10, 1)), 'labels': np.full(10, 'X')},
            {'features': np.ones((10, 1)), 'labels': np.full(10, 'D')},
        ])
        transition = np.exp(model['log_transitions'])
        np.testing.assert_allclose(transition[0], [10 / 11, 1 / 11])
        np.testing.assert_allclose(transition[1], [1 / 11, 10 / 11])

    def test_invalid_features_and_configuration_are_rejected(self):
        with self.assertRaises(ValueError):
            temporal.context([[float('nan')]])
        with self.assertRaises(ValueError):
            temporal.fit([], ridge=0)
        with self.assertRaises(ValueError):
            temporal.fit([{'features': [[1]], 'labels': ['Z']}])

    def test_fixed_corpus_has_distinct_texts_and_all_splits(self):
        plan = json.loads(Path(__file__).with_name('corpus_plan.json').read_text(encoding='utf8'))
        self.assertEqual(len(validate_plan(plan)), 20)
        duplicate = copy.deepcopy(plan)
        duplicate['recordings'][6]['text'] = '  ' + duplicate['recordings'][0]['text'].upper() + ' '
        with self.assertRaises(ValueError):
            validate_plan(duplicate)
        missing = copy.deepcopy(plan)
        missing['recordings'] = [r for r in missing['recordings'] if r['split'] != 'dev']
        with self.assertRaises(ValueError):
            validate_plan(missing)


if __name__ == '__main__':
    unittest.main()
