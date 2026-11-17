import base64
import importlib.util
import unittest
import numpy as np
import temporal
from boosted_classifier import VERSION, tree_context, decode


class BoostedTests(unittest.TestCase):
    def model(self):
        return {'classes': ['A', 'B'], 'closure_penalty': 0., 'transition_strength': 0.}

    def test_context_preserves_file_edges_without_crossing_recordings(self):
        values = np.array([[1, 2], [3, 4], [5, 6]], dtype=np.float32)
        result = tree_context(values)
        self.assertEqual(result.dtype, np.float32)
        np.testing.assert_allclose(result, temporal.context(values))
        self.assertTrue(np.all(tree_context(np.ones((2, 2))) == 1))

    def test_closure_penalty_changes_uncertain_but_not_confident_closures(self):
        p = np.array([[.55, .45], [.9, .1]])
        np.testing.assert_array_equal(decode(self.model(), p), ['A', 'A'])
        m = self.model(); m['closure_penalty'] = .25
        np.testing.assert_array_equal(decode(m, p), ['B', 'A'])

    def test_invalid_probabilities_are_rejected(self):
        for p in (np.array([[.9, .9]]), np.array([[np.nan, .5]]), np.array([[-.1, 1.1]])):
            with self.assertRaises(ValueError): decode(self.model(), p)

    @unittest.skipUnless(importlib.util.find_spec('xgboost'), 'XGBoost is installed only in the experimental environment')
    def test_trained_model_exports_and_restores_predictions_without_pickle(self):
        import xgboost as xgb
        values = np.r_[np.zeros((60, 2)), np.ones((60, 2))].astype(np.float32)
        labels = np.r_[np.zeros(60), np.ones(60)]
        booster = xgb.train({'objective': 'multi:softprob', 'num_class': 2, 'max_depth': 2,
                             'eta': 1, 'nthread': 1, 'seed': 1}, xgb.DMatrix(tree_context(values), label=labels), num_boost_round=4)
        model = {'version': VERSION, 'classes': ['B', 'X'], 'closure_penalty': 0., 'transition_strength': 0.,
                 'offsets': list(temporal.OFFSETS), 'booster_ubj': base64.b64encode(booster.save_raw(raw_format='ubj')).decode()}
        predicted = temporal.predict(model, values)
        expected = np.array(['B', 'X'])[labels.astype(int)]
        self.assertGreater(np.mean(predicted == expected), .95)
        np.testing.assert_array_equal(predicted, temporal.predict(model, values))
