import unittest

import numpy as np

from classifier import audio_features
from rhythm_features import PROFILE, timing_features, features_for_model, row_features
from build_expanded_plan import make_additions
from narration import PHRASES


class RhythmFeatureTests(unittest.TestCase):
    def sample(self):
        rate = 16000
        tone = .2 * np.sin(2 * np.pi * 250 * np.arange(3200) / rate)
        return np.r_[tone, np.zeros(3200), tone], rate

    def test_timing_channels_preserve_audio_grid_and_add_pause_durations(self):
        samples, rate = self.sample()
        base, times, hop = audio_features(samples, rate)
        extended, new_times, new_hop = timing_features(samples, rate)
        self.assertEqual(extended.shape, (len(base), 36))
        np.testing.assert_array_equal(extended[:, :26], base)
        np.testing.assert_array_equal(times, new_times)
        self.assertEqual(hop, new_hop)
        self.assertTrue(np.isfinite(extended).all())
        middle = int(.3 / hop)
        self.assertEqual(extended[middle, 27], 1)
        self.assertGreater(extended[middle, 28], 0)
        self.assertGreater(extended[middle, 29], 0)

    def test_silence_is_finite_and_does_not_invent_energy_onsets(self):
        extended, _, _ = timing_features(np.zeros(1601), 16000)
        self.assertTrue(np.isfinite(extended).all())
        self.assertTrue(np.all(extended[:, 27] == 1))
        self.assertTrue(np.all(extended[:, 35] == 0))

    def test_duration_channels_are_not_just_volume(self):
        samples, rate = self.sample()
        a, _, _ = timing_features(samples, rate)
        b, _, _ = timing_features(samples * .5, rate)
        np.testing.assert_array_equal(a[:, 27:32], b[:, 27:32])

    def test_old_and_new_models_require_their_exact_feature_profiles(self):
        samples, rate = self.sample()
        self.assertEqual(features_for_model({}, samples, rate)[0].shape[1], 26)
        model = {'feature_profile': PROFILE}
        new = features_for_model(model, samples, rate)[0]
        self.assertEqual(new.shape[1], 36)
        with self.assertRaises(ValueError):
            row_features(model, {'features': np.zeros((1, 26))})
        with self.assertRaises(ValueError):
            features_for_model({'feature_profile': 'unknown'}, samples, rate)
        np.testing.assert_array_equal(row_features(model, {'timing_features': new}), new)

    def test_new_corpus_has_four_times_as_many_reserved_advice_per_voice(self):
        rows = make_additions()['recordings']
        self.assertEqual(len(rows), 96)
        for language in ('es', 'en'):
            self.assertEqual(sum(r['language'] == language and r['split'] == 'test' for r in rows), 16)
            for row in [r for r in rows if r['language'] == language]:
                self.assertTrue(row['text'].startswith(PHRASES[language][0]))
                self.assertTrue(row['text'].endswith(PHRASES[language][1]))


if __name__ == '__main__':
    unittest.main()
