import importlib.util
import unittest
import numpy as np
import temporal
from neural_temporal import VERSION, OFFSETS, context, normalize, export_network, probabilities_from_context
from reference_quality import boundary_mask, apply_quality


class NeuralTemporalTests(unittest.TestCase):
    def test_context_stays_within_recording(self):
        first = context(np.array([[1.], [2.]]))
        second = context(np.array([[10.], [20.]]))
        self.assertEqual(first.shape, (2,7))
        self.assertLessEqual(first.max(), 2)
        self.assertGreaterEqual(second.min(), 10)

    def test_mixed_boundary_excluded_but_safe_interior_kept(self):
        # 40 ms window: [20,60) crosses start; [40,80) is safe; [80,120) crosses end.
        mask = boundary_mask([{'start_sample':40, 'end_sample':100}], 20, 1000)
        self.assertTrue(mask[4])
        self.assertFalse(mask[6])
        self.assertTrue(mask[10])
        self.assertFalse(mask[15])

    def test_reference_sidecar_does_not_mutate_labels_or_quarantine_test(self):
        row = {'id':'test', 'language':'en', 'split':'test', 'sha256_pcm':'abc',
               'labels':np.array(['B']*20), 'weak_labels':np.array(['B']*20)}
        result = apply_quality(row, [{'start_sample':40, 'end_sample':100}], 1000)
        self.assertEqual(result['quarantined_training_windows'], [])
        np.testing.assert_array_equal(row['labels'], row['weak_labels'])

    def test_bad_normalizer_rejected(self):
        with self.assertRaises(ValueError): normalize(np.ones((2,7)), np.zeros(7), np.zeros(7))

    @unittest.skipUnless(importlib.util.find_spec('sklearn'), 'experimental sklearn required')
    def test_export_matches_trained_multiclass_network_and_dispatch(self):
        from sklearn.neural_network import MLPClassifier
        x = np.random.default_rng(2).normal(size=(50,2))
        values = context(x)
        mean, scale = values.mean(0), np.maximum(values.std(0), .05)
        normalized = normalize(values,mean,scale)
        y = np.arange(50)%3
        network = MLPClassifier(hidden_layer_sizes=(64,32),random_state=4)
        network.partial_fit(normalized,y,classes=np.arange(3),sample_weight=np.ones(50))
        model = {'version':VERSION, 'offsets':list(OFFSETS), 'classes':['B','C','X'],
                 'mean':mean.tolist(), 'scale':scale.tolist(), 'network':export_network(network),
                 'closure_penalty':0., 'transition_strength':0.}
        p = probabilities_from_context(model, values)
        np.testing.assert_allclose(p,network.predict_proba(normalized),atol=1e-12)
        np.testing.assert_array_equal(temporal.predict(model,x),np.array(model['classes'])[p.argmax(1)])
