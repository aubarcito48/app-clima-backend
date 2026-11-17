import base64
import importlib.util
import io
import unittest
import numpy as np
import temporal
from boosted_classifier import tree_context
from forest_classifier import VERSION, export_forest, load_forest, probabilities_from_arrays


class ForestTests(unittest.TestCase):
    def payload(self, cyclic=False):
        output = io.BytesIO()
        np.savez_compressed(output, roots=np.array([0]), left=np.array([0 if cyclic else 1, -1, -1]),
            right=np.array([2, -1, -1]), feature=np.array([2, -2, -2]), threshold=np.array([.5, -2., -2.]),
            probability=np.array([[.5, .5], [1., 0.], [0., 1.]]))
        return base64.b64encode(output.getvalue()).decode()

    def test_portable_routing_and_model_dispatch(self):
        features = np.array([[0.], [1.]], dtype=np.float32)
        model = {'version': VERSION, 'classes': ['B', 'X'], 'closure_penalty': 0., 'transition_strength': 0.,
                 'offsets': list(temporal.OFFSETS), 'max_depth': 1, 'forest_npz': self.payload()}
        np.testing.assert_array_equal(temporal.predict(model, features), ['B', 'X'])

    def test_cyclic_tree_is_rejected(self):
        with self.assertRaises(ValueError): load_forest(self.payload(cyclic=True))

    def test_wrong_feature_layout_is_rejected(self):
        arrays = load_forest(self.payload())
        with self.assertRaises(ValueError): probabilities_from_arrays(arrays, np.ones((2, 1)), 1)

    @unittest.skipUnless(importlib.util.find_spec('sklearn'), 'sklearn exists only in the experimental environment')
    def test_native_multiclass_probabilities_survive_portable_export(self):
        from sklearn.ensemble import RandomForestClassifier
        rng = np.random.default_rng(51)
        features = rng.normal(size=(200, 3)).astype(np.float32)
        labels = np.where(features[:, 0] < -.3, 0, np.where(features[:, 1] > .4, 1, 2))
        values = tree_context(features)
        forest = RandomForestClassifier(n_estimators=8, max_depth=4, random_state=3, n_jobs=1).fit(values, labels)
        actual = probabilities_from_arrays(load_forest(export_forest(forest)), values, 4)
        np.testing.assert_allclose(actual, forest.predict_proba(values), atol=1e-12)
