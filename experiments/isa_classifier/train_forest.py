"""Fixed RF grid; same corrected labels, feature grids and decoder as XGBoost."""
import os
for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'
import argparse
import copy
import gc
import json
from pathlib import Path
import numpy as np
import sklearn
from sklearn.ensemble import RandomForestClassifier
import temporal
from boosted_classifier import tree_context, decode
from forest_classifier import VERSION, export_forest
from phoneme_identity import PROFILE
from pause_labels import PROFILE as PAUSE_PROFILE
from train_temporal import load_corpus
from verified_training_data import prepare_language
from train_boosted import summary, pause_report
from train_phonetic import grouped_advice_score
from train_rhythm import measure
from classifier import timeline


def reference_rows(rows, model, corpus):
    """An expanded training vocabulary must not alter frozen-model inputs."""
    from classifier import read_recording
    from phoneme_identity import identity_features
    result = []
    for row in rows:
        if row['identity_vocabulary'] == model['phoneme_vocabulary']:
            result.append(row)
            continue
        samples, rate, _, fingerprint = read_recording(corpus.parent / row['file'])
        info = json.loads((corpus.parent / row['phones_file']).read_text(encoding='utf8'))
        info['sha256_pcm'] = fingerprint
        features, _, _ = identity_features(samples, rate, info, model['phoneme_vocabulary'])
        result.append({**row, 'identity_features': features,
                       'identity_vocabulary': model['phoneme_vocabulary']})
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--corpus', type=Path, required=True)
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--reference-label', default='repaired XGBoost')
    p.add_argument('--candidate-label', default='Random Forest')
    args = p.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    rows, manifest = load_corpus(args.corpus)
    report = {'status': 'local_random_forest_comparison', 'label_profile': PAUSE_PROFILE,
              'primary_metric': 'advice excluding verified inserted pauses; phrase groups',
              'sklearn_version': sklearn.__version__, 'plan_sha256': manifest['plan_sha256'], 'languages': {}}
    for language in ('es', 'en'):
        subset, vocabulary = prepare_language(rows, language, args.corpus)
        train, dev, test = [[r for r in subset if r['split'] == split] for split in ('train', 'dev', 'test')]
        frozen = json.loads((args.reference/f'hybrid-{language}.json').read_text())
        if frozen.get('label_profile') != PAUSE_PROFILE: raise ValueError('Comparison requires repaired pause labels')
        frozen_dev = reference_rows(dev, frozen, args.corpus)
        frozen_test = reference_rows(test, frozen, args.corpus)
        _, baseline_dev = measure(frozen_dev, frozen)
        gate = summary(dev, baseline_dev)
        classes = sorted(set(np.concatenate([r['labels'] for r in train]).tolist()))
        codes = np.concatenate([np.array([classes.index(c) for c in r['labels']]) for r in train])
        values = np.concatenate([tree_context(r['identity_features']) for r in train])
        dev_context = [tree_context(r['identity_features']) for r in dev]
        weights = temporal.balance_weights(codes, len(classes), frozen['balance'], 4.)*np.concatenate([r['focus'] for r in train])
        weights /= weights.mean()
        transitions = np.ones((len(classes), len(classes)))
        for row in train:
            y = np.array([classes.index(c) for c in row['labels']]); np.add.at(transitions, (y[:-1], y[1:]), 1)
        transitions /= transitions.sum(axis=1, keepdims=True)
        candidates, winner, winner_score, fallback, fallback_score = [], None, None, None, None
        for depth in (12, 20):
            for leaf in (3, 8):
                params = dict(n_estimators=120, max_depth=depth, min_samples_leaf=leaf, max_features='sqrt',
                    bootstrap=True, max_samples=.8, criterion='gini', n_jobs=2, random_state=20261116)
                forest = RandomForestClassifier(**params).fit(values, codes, sample_weight=weights)
                if forest.classes_.tolist() != list(range(len(classes))): raise ValueError('Forest class order changed')
                exported = export_forest(forest)
                from forest_classifier import load_forest, probabilities_from_arrays
                # Check export against the native implementation on dev, never tune on test.
                native = [forest.predict_proba(x) for x in dev_context]
                np.testing.assert_allclose(probabilities_from_arrays(load_forest(exported), dev_context[0], depth), native[0], atol=1e-12)
                header = {'version': VERSION, 'feature_profile': PROFILE, 'label_profile': PAUSE_PROFILE,
                    'corpus_plan_sha256': manifest['plan_sha256'],
                    'phoneme_vocabulary': vocabulary, 'language': language, 'classes': classes,
                    'offsets': list(temporal.OFFSETS), 'log_transitions': np.log(transitions).tolist(),
                    'balance': frozen['balance'], 'max_depth': depth, 'min_samples_leaf': leaf,
                    'params': params, 'forest_npz': exported,
                    'training_plan_sha256': manifest['plan_sha256'],
                    'training': [{'file': r['file'], 'sha256_pcm': r['sha256_pcm']} for r in train]}
                for penalty in (0., .25):
                    for strength in (0., .05):
                        model = {**header, 'closure_penalty': penalty, 'transition_strength': strength}
                        stats = summary(dev, [decode(model, probability) for probability in native])
                        eligible = (stats['false_closure'] <= gate['false_closure']+.002
                            and stats['pause_closure'] >= gate['pause_closure']-.01 and stats['recall_a'] >= gate['recall_a']-.03)
                        score = stats['f1'], stats['agreement']
                        candidates.append({'depth': depth, 'min_leaf': leaf, 'penalty': penalty, 'transition': strength,
                                           'eligible': eligible, **stats})
                        if fallback_score is None or score > fallback_score: fallback, fallback_score = copy.deepcopy(model), score
                        if eligible and (winner_score is None or score > winner_score): winner, winner_score = copy.deepcopy(model), score
                print(json.dumps({'language': language, 'depth': depth, 'min_leaf': leaf, 'stage': 'fit_complete'}), flush=True)
                del forest, native; gc.collect()
        passed = winner is not None; model = winner if passed else fallback
        (args.output/f'hybrid-{language}.json').write_text(json.dumps(model), encoding='utf8')
        new, predicted = measure(test, model); old, old_predicted = measure(frozen_test, frozen)
        for result, predictions in [(new, predicted), (old, old_predicted)]:
            result['grouped_advice'] = grouped_advice_score(test, predictions)
            result['pause_details'] = pause_report(test, predictions)
        report['languages'][language] = {'train': len(train), 'dev': len(dev), 'test': len(test),
            'test_groups': len({r['group_id'] for r in test}), 'dev_guardrails_passed': passed,
            'dev_baseline': gate, 'candidates': candidates,
            'selection': {k: model[k] for k in ('max_depth', 'min_samples_leaf', 'balance', 'closure_penalty', 'transition_strength')},
            'boosted': new, 'identity': old, 'model_names': {'boosted': args.candidate_label, 'identity': args.reference_label}}
        for row, prediction in zip(test, predicted):
            (args.output/f"prediction-{row['id']}.json").write_text(json.dumps(timeline(prediction, row['hop'], row['duration'])))
        print(json.dumps({'language': language, 'guardrails_passed': passed, 'test': {
            name: {key: result['grouped_advice'][key] for key in ('mean_group_agreement', 'mean_group_macro_f1')}
            for name, result in [('forest', new), ('xgboost', old)]}}), flush=True)
        for row in subset:
            for key in ('identity_features', 'phonetic_features', 'timing_features'): row.pop(key, None)
        del values, dev_context, subset, train, dev, test; gc.collect()
    (args.output/'evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf8')


if __name__ == '__main__': main()
