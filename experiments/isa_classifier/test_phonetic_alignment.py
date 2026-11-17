import unittest
from phonetic_alignment import grouped_durations, phone_shapes, expand_diphthongs, append_cue


class PhoneticAlignmentTests(unittest.TestCase):
    def test_multi_id_phone_padding_and_total(self):
        mapping = {'^': [1], '_': [0], '$': [2], 'a': [3, 4]}
        rows = grouped_durations(['a'], mapping, [1, 0, 3, 4, 0, 2], [0, 2, 4, 3, 1, 2], 12)
        self.assertEqual([r['samples'] for r in rows], [2, 8, 2])
        with self.assertRaises(ValueError):
            grouped_durations(['a'], mapping, [1, 0, 3, 4, 0, 2], [0, 2, 4, 3, 1, 2], 13)

    def test_bad_or_missing_alignment_fails(self):
        for counts in ([float('nan')], [-1], [.5]):
            with self.assertRaises(ValueError):
                grouped_durations([], {}, [1], counts, 1)
        with self.assertRaises(ValueError):
            phone_shapes([{'phoneme': 'unknown'}], 'en')

    def test_stress_length_and_space_never_become_rest(self):
        rows = [{'phoneme': p} for p in ['^', 'ˈ', 'a', 'ː', ' ', 'm', '$']]
        self.assertEqual(phone_shapes(rows, 'en'), ['X', 'D', 'D', 'D', 'D', 'A', 'X'])

    def test_diphthong_has_transition_and_preserves_samples(self):
        rows = expand_diphthongs([{'phoneme': 'eɪ', 'samples': 101}])
        self.assertEqual(sum(r['samples'] for r in rows), 101)
        self.assertEqual(phone_shapes(rows, 'en'), ['C', 'B'])
        self.assertTrue(all(r['internal_boundary'] == 'estimated_equal_split' for r in rows))

    def test_merge_adjacent_shapes_without_losing_closure(self):
        cues = []
        for start, end, shape in [(0, .1, 'B'), (.1, .2, 'B'), (.2, .23, 'A'), (.23, .3, 'B')]:
            append_cue(cues, start, end, shape)
        self.assertEqual(len(cues), 3)
        self.assertEqual(cues[1], {'start': .2, 'end': .23, 'value': 'A'})
