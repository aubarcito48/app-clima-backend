from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import numpy as np

from classifier import metrics
from generate_corpus import replace_manifest
from temporal import balance_weights


class BalanceTests(unittest.TestCase):
    def test_no_balancing_gives_equal_weights(self):
        np.testing.assert_array_equal(balance_weights(np.array([0] * 99 + [1]), 2, 0, 4), np.ones(100))

    def test_rare_classes_gain_weight_without_infinite_oversampling(self):
        labels = np.array([0] * 99 + [1])
        weights = balance_weights(labels, 2, 1, 4)
        self.assertGreater(weights[-1], weights[0])
        self.assertAlmostEqual(float(weights.mean()), 1)
        self.assertLess(weights[-1] / weights[0], 8)
        with self.assertRaises(ValueError):
            balance_weights(labels, 2, .5, .5)

    def test_zero_recall_for_rare_class_is_visible_despite_high_agreement(self):
        result = metrics(np.array(['B'] * 99 + ['D']), np.array(['B'] * 100))
        self.assertAlmostEqual(result['frame_agreement'], .99)
        self.assertAlmostEqual(result['balanced_recall'], .5)
        self.assertEqual(result['f1_by_shape']['D'], 0)
        self.assertLess(result['macro_f1'], .5)

    def test_false_positive_only_class_is_penalized_in_macro_f1(self):
        result = metrics(np.array(['X', 'X']), np.array(['X', 'D']))
        self.assertAlmostEqual(result['macro_f1'], 1 / 3)
        self.assertEqual(result['precision_by_shape']['D'], 0)

    def test_windows_atomic_replace_retries_only_bounded_permission_errors(self):
        source = Mock(spec=Path)
        source.replace.side_effect = [PermissionError(), None]
        with patch('generate_corpus.time.sleep') as sleep:
            replace_manifest(source, Path('target.json'))
        self.assertEqual(source.replace.call_count, 2)
        sleep.assert_called_once_with(.1)
        source.replace.reset_mock()
        source.replace.side_effect = PermissionError()
        with patch('generate_corpus.time.sleep'), self.assertRaises(PermissionError):
            replace_manifest(source, Path('target.json'))
        self.assertEqual(source.replace.call_count, 6)


if __name__ == '__main__':
    unittest.main()
