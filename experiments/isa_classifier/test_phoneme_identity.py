import hashlib
import struct
import unittest
import numpy as np
from phoneme_identity import vocabulary_from_training, identity_features, GAP, UNKNOWN, PROFILE
from phonetic_features import hybrid_features
from rhythm_features import features_for_model, row_features


class PhonemeIdentityTests(unittest.TestCase):
    def fixture(self):
        rate = 16000; samples = np.zeros(rate)
        return samples, rate, {'sha256_pcm': hashlib.sha256(struct.pack('<I', rate) + b'\0\0' * rate).hexdigest(),
            'phonemes': [{'phoneme': 'a', 'start': 0, 'end': .4}, {'phoneme': 'm', 'start': .6, 'end': 1}],
            'cues': [{'value': 'D', 'start': 0, 'end': .4}, {'value': 'X', 'start': .4, 'end': .6}, {'value': 'A', 'start': .6, 'end': 1}]}

    def test_identity_preserves_existing_features_and_separates_gap(self):
        samples, rate, alignment = self.fixture()
        vocabulary = vocabulary_from_training([alignment])
        self.assertEqual(vocabulary, [GAP, UNKNOWN, 'a', 'm'])
        x, times, _ = identity_features(samples, rate, alignment, vocabulary)
        np.testing.assert_array_equal(x[:, :48], hybrid_features(samples, rate, alignment)[0])
        np.testing.assert_array_equal(x[:, 48:].sum(axis=1), np.ones(len(x)))
        self.assertTrue(np.all(x[(times >= .4) & (times < .6), 48] == 1))

    def test_unseen_phone_uses_unknown_without_growing_training_vocabulary(self):
        samples, rate, alignment = self.fixture()
        vocabulary = vocabulary_from_training([alignment])
        alignment['phonemes'][0]['phoneme'] = 's'
        x, times, _ = features_for_model({'feature_profile': PROFILE, 'phoneme_vocabulary': vocabulary}, samples, rate, alignment=alignment)
        self.assertNotIn('s', vocabulary)
        self.assertTrue(np.all(x[times < .4, 49] == 1))

    def test_missing_vocabulary_is_rejected(self):
        samples, rate, alignment = self.fixture()
        with self.assertRaises(ValueError):
            identity_features(samples, rate, alignment, None)

    def test_same_size_but_reordered_vocabulary_is_rejected(self):
        with self.assertRaises(ValueError):
            row_features({'feature_profile': PROFILE, 'phoneme_vocabulary': [GAP, UNKNOWN, 'a', 'm']},
                         {'identity_features': np.zeros((2, 52)), 'identity_vocabulary': [GAP, UNKNOWN, 'm', 'a']})
