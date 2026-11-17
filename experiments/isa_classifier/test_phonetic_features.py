import hashlib
import struct
import unittest
import numpy as np
from phonetic_features import hybrid_features, PROFILE
from rhythm_features import features_for_model, row_features, timing_features


class HybridFeatureTests(unittest.TestCase):
    def fixture(self):
        rate = 16000
        samples = np.zeros(rate)
        info = {'sha256_pcm': hashlib.sha256(struct.pack('<I', rate) + b'\0\0' * rate).hexdigest(),
                'cues': [{'start': 0, 'end': .4, 'value': 'D'}, {'start': .4, 'end': .6, 'value': 'X'},
                         {'start': .6, 'end': 1, 'value': 'A'}],
                'phonemes': [{'start': 0, 'end': .4}, {'start': .6, 'end': 1}]}
        return samples, rate, info

    def test_preserves_timing_inputs_and_encodes_true_inserted_gap(self):
        samples, rate, info = self.fixture()
        x, times, hop = hybrid_features(samples, rate, info)
        self.assertEqual(x.shape[1], 48)
        np.testing.assert_array_equal(x[:, :36], timing_features(samples, rate)[0])
        np.testing.assert_array_equal(x[:, 36:45].sum(axis=1), np.ones(len(x)))
        self.assertTrue(np.isfinite(x).all())
        self.assertTrue(np.all(x[(times >= .4) & (times < .6), -3:] == 0))
        np.testing.assert_array_equal(features_for_model({'feature_profile': PROFILE}, samples, rate, alignment=info)[0], x)

    def test_missing_or_other_pcm_is_rejected(self):
        samples, rate, info = self.fixture()
        with self.assertRaises(ValueError):
            features_for_model({'feature_profile': PROFILE}, samples, rate)
        info['sha256_pcm'] = 'different'
        with self.assertRaises(ValueError):
            hybrid_features(samples, rate, info)
        with self.assertRaises(ValueError):
            row_features({'feature_profile': PROFILE}, {})

    def test_overlapping_phonemes_rejected(self):
        samples, rate, info = self.fixture()
        info['phonemes'][1]['start'] = .3
        with self.assertRaises(ValueError):
            hybrid_features(samples, rate, info)
