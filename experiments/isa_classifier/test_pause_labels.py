import unittest
import numpy as np
from pause_labels import verified_intervals, pause_masks, corrected_labels
from classifier import audio_features


class PauseLabelTests(unittest.TestCase):
    def fixture(self, milliseconds=160):
        rate = 16000; a = 3200; b = a + rate * milliseconds // 1000
        samples = np.r_[np.ones(a) * .1, np.zeros(b-a), np.ones(3200) * .1]
        phones = [{'start': 0, 'end': a/rate}, {'start': b/rate, 'end': len(samples)/rate}]
        performance = [{'speech_end': a/rate, 'until': b/rate}]
        return samples, rate, phones, performance

    def test_only_full_silent_analysis_windows_are_relabelled(self):
        samples, rate, phones, performance = self.fixture()
        intervals = verified_intervals(samples, rate, performance, phones)
        features, times, _ = audio_features(samples, rate)
        full, safe = pause_masks(intervals, len(features), rate, times)
        self.assertGreater(full.sum(), safe.sum()); self.assertGreater(safe.sum(), 0)
        original = np.full(len(features), 'A')
        cleaned = corrected_labels(original, safe)
        self.assertTrue(np.all(cleaned[safe] == 'X'))
        np.testing.assert_array_equal(cleaned[~safe], original[~safe])
        self.assertTrue(np.all(original == 'A'), 'Preserve the original weak labels')

    def test_chunk_gap_is_verified_but_20ms_has_no_40ms_interior(self):
        samples, rate, phones, _ = self.fixture(20)
        intervals = verified_intervals(samples, rate, [], phones)
        features, times, _ = audio_features(samples, rate)
        full, safe = pause_masks(intervals, len(features), rate, times)
        self.assertEqual(intervals[0]['source'], 'inserted_chunk_pause')
        self.assertTrue(full.any()); self.assertFalse(safe.any())

    def test_nonzero_pcm_or_unknown_gaps_cannot_be_called_silence(self):
        samples, rate, phones, performance = self.fixture()
        samples[3300] = 1/32768
        with self.assertRaises(ValueError): verified_intervals(samples, rate, performance, phones)
        samples, rate, phones, _ = self.fixture(60)
        with self.assertRaises(ValueError): verified_intervals(samples, rate, [], phones)

    def test_natural_silence_inside_a_phone_is_not_automatically_relabelled(self):
        samples, rate, _, _ = self.fixture()
        phones = [{'start': 0, 'end': len(samples)/rate}]
        self.assertEqual(verified_intervals(samples, rate, [], phones), [])

    def test_metadata_overlapping_a_phone_is_rejected(self):
        samples, rate, _, performance = self.fixture()
        with self.assertRaises(ValueError):
            verified_intervals(samples, rate, performance, [{'start': 0, 'end': len(samples)/rate}])
