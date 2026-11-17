import copy
import unittest
from rate_expansion_plan import make_plan
from generate_corpus import validate_plan
import numpy as np
from train_phonetic import grouped_advice_score


class RateExpansionTests(unittest.TestCase):
    def test_duplicating_rate_variant_does_not_double_phrase_weight(self):
        a = {'id': 'a', 'group_id': 'a', 'labels': np.array(['D']), 'advice_mask': np.array([True])}
        b = {'id': 'b', 'group_id': 'b', 'labels': np.array(['C']), 'advice_mask': np.array([True])}
        first = grouped_advice_score([a, b], [np.array(['D']), np.array(['D'])])
        repeated = grouped_advice_score([a, a, b], [np.array(['D']), np.array(['D']), np.array(['D'])])
        self.assertEqual(first['mean_group_agreement'], repeated['mean_group_agreement'])
        self.assertEqual(repeated['phrase_groups'], 2)
    def manifest(self):
        return {'recordings': [{**r, 'variant': 'baseline'} for r in make_plan()], 'augmentation_profile': 'paired-rate-v1'}
    def test_new_group_split_counts_and_content_limits(self):
        manifest = self.manifest()
        validate_plan(manifest)
        for lang in ('es', 'en'):
            rows = [r for r in manifest['recordings'] if r['language'] == lang]
            self.assertEqual([sum(r['split'] == split for r in rows) for split in ('train', 'dev', 'test')], [16, 4, 8])
            self.assertTrue(all(len(r['advice'].split()) <= 40 for r in rows))
    def test_pair_allowed_only_with_same_split_and_group(self):
        m = self.manifest()
        extra = {**m['recordings'][0], 'id': 'es-extra-auto', 'variant': 'automatic'}
        m['recordings'].append(extra)
        validate_plan(m)
        for key, value in [('split', 'test'), ('group_id', 'different')]:
            bad = copy.deepcopy(m); bad['recordings'][-1][key] = value
            with self.assertRaises(ValueError): validate_plan(bad)
        bad = copy.deepcopy(m); bad['recordings'].append({**extra, 'id': 'es-extra-third'})
        with self.assertRaises(ValueError): validate_plan(bad)
        del m['augmentation_profile']
        with self.assertRaises(ValueError): validate_plan(m)
