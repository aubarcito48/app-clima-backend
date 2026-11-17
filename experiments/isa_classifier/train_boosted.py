"""Fixed train/dev boosted experiment; no test-driven calibration."""
import os
for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'
import argparse
import base64
import copy
import gc
import json
from pathlib import Path
import numpy as np
import xgboost as xgb
import temporal
from boosted_classifier import VERSION, tree_context, probabilities, decode
from classifier import read_recording, labels_at, metrics, timeline
from narration import advice_spans, performance_rows
from phoneme_identity import PROFILE, identity_features, vocabulary_from_training
from phonetic_features import hybrid_features
from rhythm_features import timing_features
from train_temporal import load_corpus
from train_short import core_mask
from train_rhythm import measure
from train_phonetic import grouped_advice_score
from pause_labels import PROFILE as PAUSE_PROFILE, verified_intervals, pause_masks, corrected_labels


def summary(rows, predictions):
    grouped = grouped_advice_score(rows, predictions)
    expected = np.concatenate([r['labels'][r['advice_mask']] for r in rows])
    actual = np.concatenate([p[r['advice_mask']] for r, p in zip(rows, predictions)])
    stats = metrics(expected, actual)
    pauses = np.concatenate([p[r['known_pause_mask']] for r, p in zip(rows, predictions)])
    return {'f1': grouped['mean_group_macro_f1'], 'agreement': grouped['mean_group_agreement'],
            'false_closure': float(np.mean(np.isin(actual, ['A', 'X']) & ~np.isin(expected, ['A', 'X']))),
            'pause_closure': float(np.mean(np.isin(pauses, ['A', 'X']))) if len(pauses) else 0.,
            'recall_a': stats['recall_by_shape'].get('A') or 0.}


def pause_report(rows, predictions):
    report = {}
    for name, key in [('verified_interior', 'safe_pause_mask'), ('legacy_segment_pauses', 'segment_pause_mask')]:
        values = np.concatenate([p[r[key]] for r, p in zip(rows, predictions)])
        report[name] = {'windows': len(values), 'closed_rate': float(np.mean(np.isin(values, ['A', 'X']))) if len(values) else None,
                        'rest_x_rate': float(np.mean(values == 'X')) if len(values) else None}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--v7', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--verified-pauses', action='store_true')
    parser.add_argument('--fixed-configuration', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows, manifest = load_corpus(args.corpus)
    rows = [r for r in rows if r['split'] != 'test' or r.get('evaluation') == 'fresh']
    report = {'status': 'local_boosted_experiment', 'reference': 'weak-rhubarb-with-verified-pause-interiors' if args.verified_pauses else 'weak-rhubarb-not-human-gold',
              'label_profile': PAUSE_PROFILE if args.verified_pauses else 'original-weak-labels',
              'primary_metric': 'advice excluding all verified inserted pauses' if args.verified_pauses else 'advice-only',
              'xgboost_version': xgb.__version__, 'plan_sha256': manifest['plan_sha256'], 'languages': {}}
    for language in ('es', 'en'):
        subset = [r for r in rows if r['language'] == language]
        infos = {r['id']: json.loads((args.corpus.parent / r['phones_file']).read_text(encoding='utf8')) for r in subset}
        vocabulary = vocabulary_from_training([infos[r['id']] for r in subset if r['split'] == 'train'])
        train_groups = {}
        for row in subset:
            if row['split'] == 'train':
                key = row.get('group_id', row['id']); train_groups[key] = train_groups.get(key, 0) + 1
        for row in subset:
            wav = args.corpus.parent / row['file']
            samples, rate, _, fingerprint = read_recording(wav)
            if fingerprint != row['sha256_pcm'] or advice_spans(wav.read_bytes(), row['duration']) != row['advice_spans']:
                raise ValueError('Training audio or advice timings changed')
            info = infos[row['id']]
            if info['text'] != row['text']:
                raise ValueError('Phonetic text mismatch')
            raw = (args.corpus.parent / row['phones_file']).parent / f'raw-{language}.wav'
            if read_recording(raw)[3] != fingerprint:
                raise ValueError('Phonetic timings belong to different audio')
            info['sha256_pcm'] = fingerprint
            row['identity_features'], times, _ = identity_features(samples, rate, info, vocabulary)
            row['identity_vocabulary'] = vocabulary
            row['phonetic_features'], _, _ = hybrid_features(samples, rate, info)
            row['timing_features'], _, _ = timing_features(samples, rate)
            row['advice_mask'] = core_mask(row)
            original_advice_mask = row['advice_mask'].copy()
            row['known_pause_mask'] = np.zeros(len(times), dtype=bool)
            for segment in performance_rows(wav.read_bytes(), row['duration']):
                row['known_pause_mask'] |= (times >= segment['speech_end']) & (times < segment['until'])
            if args.verified_pauses:
                row['segment_pause_mask'] = row['known_pause_mask'].copy()
                intervals = verified_intervals(samples, rate, performance_rows(wav.read_bytes(), row['duration']), info['phonemes'])
                full, safe = pause_masks(intervals, len(times), rate, times)
                row['weak_labels'] = row['labels'].copy()
                row['labels'] = corrected_labels(row['labels'], safe)
                row['safe_pause_mask'] = safe
                row['known_pause_mask'] = full
                row['advice_mask'] &= ~full
            row['focus'] = np.where(original_advice_mask, 1., .25) / train_groups.get(row.get('group_id', row['id']), 1)
        train = [r for r in subset if r['split'] == 'train']
        dev = [r for r in subset if r['split'] == 'dev']
        test = [r for r in subset if r['split'] == 'test']
        frozen = json.loads((args.reference / f'hybrid-{language}.json').read_text())
        reference_dev, reference_predictions = measure(dev, frozen)
        gate = summary(dev, reference_predictions)
        classes = sorted(set(np.concatenate([r['labels'] for r in train]).tolist()))
        codes = np.concatenate([np.array([classes.index(c) for c in r['labels']]) for r in train])
        values = np.concatenate([tree_context(r['identity_features']) for r in train])
        dtrain = xgb.DMatrix(values, label=codes, nthread=2)
        del values; gc.collect()
        transitions = np.ones((len(classes), len(classes)))
        for row in train:
            y = np.array([classes.index(c) for c in row['labels']])
            np.add.at(transitions, (y[:-1], y[1:]), 1)
        transitions /= transitions.sum(axis=1, keepdims=True)
        focus = np.concatenate([r['focus'] for r in train])
        candidates, winner, winner_score, fallback, fallback_score = [], None, None, None, None
        fixed = json.loads((args.fixed_configuration / f'hybrid-{language}.json').read_text()) if args.fixed_configuration else None
        for depth in ([fixed['max_depth']] if fixed else (3, 5)):
            for balance in ([fixed['balance']] if fixed else (.25, .5)):
                weights = temporal.balance_weights(codes, len(classes), balance, 4.) * focus
                dtrain.set_weight(weights / weights.mean())
                params = {'objective': 'multi:softprob', 'num_class': len(classes), 'tree_method': 'hist',
                    'max_bin': 64, 'max_depth': depth, 'eta': .08, 'lambda': 10, 'min_child_weight': 10,
                    'subsample': .85, 'colsample_bytree': .8, 'seed': 20261116, 'nthread': 2, 'verbosity': 0}
                booster = xgb.train(params, dtrain, num_boost_round=160)
                header = {'version': VERSION, 'feature_profile': PROFILE, 'phoneme_vocabulary': vocabulary,
                    'label_profile': report['label_profile'],
                    'language': language, 'classes': classes, 'offsets': list(temporal.OFFSETS),
                    'log_transitions': np.log(transitions).tolist(), 'balance': balance, 'max_depth': depth,
                    'rounds': 160, 'params': params, 'training': [{'file': r['file'], 'sha256_pcm': r['sha256_pcm']} for r in train],
                    'booster_ubj': base64.b64encode(booster.save_raw(raw_format='ubj')).decode()}
                dev_probabilities = [probabilities(booster, r['identity_features']) for r in dev]
                for penalty in ([fixed['closure_penalty']] if fixed else (0., .25)):
                    for strength in ([fixed['transition_strength']] if fixed else (0., .05)):
                        model = {**header, 'closure_penalty': penalty, 'transition_strength': strength}
                        stats = summary(dev, [decode(model, p) for p in dev_probabilities])
                        eligible = (stats['false_closure'] <= gate['false_closure'] + .002
                                    and stats['pause_closure'] >= gate['pause_closure'] - .01
                                    and stats['recall_a'] >= gate['recall_a'] - .03)
                        score = (stats['f1'], stats['agreement'])
                        candidates.append({'depth': depth, 'balance': balance, 'penalty': penalty,
                                           'transition': strength, 'eligible': eligible, **stats})
                        if fallback_score is None or score > fallback_score:
                            fallback, fallback_score = copy.deepcopy(model), score
                        if eligible and (winner_score is None or score > winner_score):
                            winner, winner_score = copy.deepcopy(model), score
                print(json.dumps({'language': language, 'depth': depth, 'balance': balance, 'stage': 'fit_complete'}), flush=True)
                del booster, dev_probabilities; gc.collect()
        passed = winner is not None
        model = winner if passed else fallback
        # Serialize the frozen choice before evaluating any test score.
        (args.output / f'hybrid-{language}.json').write_text(json.dumps(model), encoding='utf8')
        selected, predicted = measure(test, model)
        selected['grouped_advice'] = grouped_advice_score(test, predicted)
        prior, prior_pred = measure(test, frozen)
        prior['grouped_advice'] = grouped_advice_score(test, prior_pred)
        v7 = json.loads((args.v7 / f'audio-{language}.json').read_text())
        original, original_pred = measure(test, v7)
        original['grouped_advice'] = grouped_advice_score(test, original_pred)
        if args.verified_pauses:
            for result, predictions in [(selected, predicted), (prior, prior_pred), (original, original_pred)]:
                result['pause_details'] = pause_report(test, predictions)
            label_audit = {}
            for split in ('train', 'dev', 'test'):
                portion = [r for r in subset if r['split'] == split]
                label_audit[split] = {'recordings': len(portion),
                    'safe_pause_windows': sum(int(r['safe_pause_mask'].sum()) for r in portion),
                    'labels_changed': sum(int(np.sum(r['labels'] != r['weak_labels'])) for r in portion),
                    'open_labels_corrected': sum(int(np.sum(r['safe_pause_mask'] & ~np.isin(r['weak_labels'], ['A', 'X']))) for r in portion)}
        report['languages'][language] = {'train': len(train), 'dev': len(dev), 'test': len(test),
            'test_groups': len({r['group_id'] for r in test}), 'vocabulary_entries': len(vocabulary),
            'dev_guardrails_passed': passed, 'dev_baseline': gate, 'candidates': candidates,
            'selection': {k: model[k] for k in ('max_depth', 'balance', 'closure_penalty', 'transition_strength')},
            'boosted': selected, 'identity': prior, 'v7': original}
        if args.verified_pauses:
            report['languages'][language]['label_audit'] = label_audit
        for row, p in zip(test, predicted):
            (args.output / f"prediction-{row['id']}.json").write_text(json.dumps(timeline(p, row['hop'], row['duration'])))
        print(json.dumps({'language': language, 'guardrails_passed': passed, 'test': {
            name: {k: r['grouped_advice'][k] for k in ('mean_group_agreement', 'mean_group_macro_f1')}
            for name, r in [('boosted', selected), ('identity', prior), ('v7', original)]}}), flush=True)
        for row in subset:
            for key in ('identity_features', 'phonetic_features', 'timing_features'):
                row.pop(key, None)
        del dtrain, infos, train, dev, test, subset; gc.collect()
    (args.output / 'evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
