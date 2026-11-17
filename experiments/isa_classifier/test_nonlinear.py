import json
import unittest

import numpy as np

import temporal


class NonlinearTests(unittest.TestCase):
    def recordings(self):
        rng = np.random.default_rng(12)
        return [{'features': np.tile(point, (30, 1)) + rng.normal(0, .01, (30, 2)),
                 'labels': np.full(30, label)} for point, label in [
                     ([-1, -1], 'A'), ([-1, 1], 'X'), ([1, -1], 'X'), ([1, 1], 'A')]]

    def test_nonlinear_model_can_learn_separated_xor_clusters(self):
        model = temporal.fit(self.recordings(), ridge=.1, nonlinear_scale=1.5)
        self.assertEqual(model['version'], temporal.NONLINEAR_VERSION)
        for point, label in [([-1.05, -1.02], 'A'), ([-1.02, 1.03], 'X'),
                             ([1.02, -1.01], 'X'), ([1.03, 1.02], 'A')]:
            result = temporal.predict(model, np.tile(point, (10, 1)))
            self.assertTrue(np.all(result == label))

    def test_json_roundtrip_keeps_predictions_and_seed(self):
        model = temporal.fit(self.recordings(), nonlinear_scale=.5)
        loaded = json.loads(json.dumps(model))
        query = np.tile([1., -1.], (12, 1))
        np.testing.assert_array_equal(temporal.predict(model, query), temporal.predict(loaded, query))
        self.assertEqual(model['nonlinear']['seed'], 20261116)

    def test_old_linear_model_without_new_fields_still_predicts(self):
        model = temporal.fit(self.recordings())
        del model['nonlinear']
        model.pop('weight_cap')
        model.pop('weight_range')
        result = temporal.predict(model, np.zeros((5, 2)))
        self.assertEqual(len(result), 5)

    def test_invalid_nonlinear_scales_rejected(self):
        for scale in (0, -1, float('nan'), float('inf')):
            with self.subTest(scale=scale), self.assertRaises(ValueError):
                temporal.fit(self.recordings(), nonlinear_scale=scale)


if __name__ == '__main__':
    unittest.main()
