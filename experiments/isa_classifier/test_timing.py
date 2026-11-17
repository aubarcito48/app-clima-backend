import unittest

import numpy as np

from analyze_timing import quiet_candidates


class TimingAnalysisTests(unittest.TestCase):
    def test_detects_synthetic_gap_with_bounded_times(self):
        rate = 16000
        tone = .2 * np.sin(2 * np.pi * 220 * np.arange(1600) / rate)
        samples = np.concatenate([tone, np.zeros(800), tone])
        rows, _, _, _ = quiet_candidates(samples, rate)
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]['start'], .1, places=2)
        self.assertAlmostEqual(rows[0]['end'], .15, places=2)
        self.assertFalse(rows[0]['verified'])
        self.assertFalse(rows[0]['word_boundary'])

    def test_short_low_energy_closure_is_not_declared_a_word_pause(self):
        rate = 16000
        samples = np.r_[np.ones(1600) * .1, np.zeros(480), np.ones(1600) * .1]
        rows, _, _, _ = quiet_candidates(samples, rate)
        self.assertEqual(rows[0]['kind'], 'quiet_short_candidate')
        self.assertFalse(rows[0]['word_boundary'])
        self.assertFalse(rows[0]['verified'])

    def test_silence_does_not_invent_words_or_sentence_boundaries(self):
        rows, threshold, energy, _ = quiet_candidates(np.zeros(16000), 16000)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['end'], 1)
        self.assertGreater(threshold, 0)
        self.assertTrue(np.isfinite(energy).all())
        self.assertNotIn('sentence_end', rows[0])


if __name__ == '__main__':
    unittest.main()
