"""Fixed small TDNN and reference-quality ablation; dev selection, fresh final test."""
import os
for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'
import argparse
import copy
import gc
import json
import time
from pathlib import Path
import numpy as np
from sklearn.neural_network import MLPClassifier
import temporal
from neural_temporal import VERSION, OFFSETS, context, normalize, export_network, probabilities_from_context
from phoneme_identity import PROFILE
from pause_labels import PROFILE as PAUSE_PROFILE, verified_intervals
from reference_quality import PROFILE as QUALITY_PROFILE, apply_quality
from classifier import read_recording, timeline
from narration import performance_rows
from train_temporal import load_corpus
from verified_training_data import prepare_language
from train_boosted import summary, pause_report
from train_rhythm import measure
from train_phonetic import grouped_advice_score
from boosted_classifier import decode


def eligible(stats, baseline):
    return (stats['false_closure'] <= baseline['false_closure']+.002
            and stats['pause_closure'] >= baseline['pause_closure']-.01
            and stats['recall_a'] >= baseline['recall_a']-.03)


def evaluate(rows, model):
    start = time.perf_counter()
    result, predictions = measure(rows, model)
    result['evaluation_seconds_including_metrics'] = time.perf_counter()-start
    result['grouped_advice'] = grouped_advice_score(rows, predictions)
    result['pause_details'] = pause_report(rows, predictions)
    return result, predictions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('corpus', 'reference', 'forest', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows, manifest = load_corpus(args.corpus)
    report = {'status': 'experimental_small_time_delay_network', 'plan_sha256': manifest['plan_sha256'],
              'reference': 'weak Rhubarb with PCM-proven inserted pause interiors; not human gold',
              'quality_profile': QUALITY_PROFILE, 'selection': 'fixed protocol, development only', 'languages': {}}
    quality = []
    for language in ('es', 'en'):
        subset, vocabulary = prepare_language(rows, language, args.corpus)
        train, dev, test = [[r for r in subset if r['split'] == split] for split in ('train', 'dev', 'test')]
        for row in subset:
            wav = args.corpus.parent/row['file']
            samples, rate, _, fingerprint = read_recording(wav)
            info_path = args.corpus.parent/row['phones_file']
            if fingerprint != read_recording(info_path.parent/f'raw-{language}.wav')[3]:
                raise ValueError('Reference correction requires original same-PCM synthesis')
            info = json.loads(info_path.read_text(encoding='utf8'))
            intervals = verified_intervals(samples, rate, performance_rows(wav.read_bytes(), row['duration']), info['phonemes'])
            quality.append(apply_quality(row, intervals, rate))
        (args.output/'reference-corrections.json').write_text(json.dumps({'profile': QUALITY_PROFILE,
            'originals_preserved': True, 'cases': quality}, indent=2), encoding='utf8')
        baseline = json.loads((args.reference/f'hybrid-{language}.json').read_text())
        forest = json.loads((args.forest/f'hybrid-{language}.json').read_text())
        _, dev_baseline = measure(dev, baseline)
        gate = summary(dev, dev_baseline)
        classes = sorted(set(np.concatenate([r['labels'] for r in train]).tolist()))
        codes = np.concatenate([np.array([classes.index(c) for c in r['labels']]) for r in train])
        train_context = np.concatenate([context(r['identity_features']) for r in train])
        mean, scale = train_context.mean(axis=0), np.maximum(train_context.std(axis=0), .05)
        values = normalize(train_context, mean, scale)
        dev_context = [context(r['identity_features']) for r in dev]
        dev_values = [normalize(x, mean, scale) for x in dev_context]
        weights = temporal.balance_weights(codes, len(classes), baseline['balance'], 4.)*np.concatenate([r['focus'] for r in train])
        border = np.concatenate([r['boundary_mask'] for r in train])
        transitions = np.ones((len(classes), len(classes)))
        for row in train:
            y = np.array([classes.index(c) for c in row['labels']])
            np.add.at(transitions, (y[:-1], y[1:]), 1)
        transitions /= transitions.sum(axis=1, keepdims=True)
        selected_arms, candidates = {}, []
        for arm in ('repaired', 'quarantined'):
            keep = ~border if arm == 'quarantined' else np.ones(len(border), bool)
            x, y, w = values[keep], codes[keep], weights[keep].copy()
            w /= w.mean()
            network = MLPClassifier(hidden_layer_sizes=(64,32), activation='relu', solver='adam',
                learning_rate_init=.001, alpha=.01, batch_size=512, random_state=20261116,
                early_stopping=False, shuffle=True)
            best, best_key = None, None
            for epoch in range(1,33):
                network.partial_fit(x, y, classes=np.arange(len(classes)), sample_weight=w)
                if epoch % 8:
                    continue
                model = {'version': VERSION, 'feature_profile': PROFILE, 'label_profile': PAUSE_PROFILE,
                    'quality_profile': QUALITY_PROFILE if arm == 'quarantined' else PAUSE_PROFILE,
                    'language': language, 'phoneme_vocabulary': vocabulary, 'classes': classes,
                    'offsets': list(OFFSETS), 'mean': mean.tolist(), 'scale': scale.tolist(),
                    'network': export_network(network), 'balance': baseline['balance'], 'epoch': epoch,
                    'arm': arm, 'log_transitions': np.log(transitions).tolist(),
                    'training': [{'file': r['file'], 'sha256_pcm': r['sha256_pcm']} for r in train]}
                native = [network.predict_proba(x) for x in dev_values]
                np.testing.assert_allclose(probabilities_from_context(model, dev_context[0]), native[0], atol=1e-12)
                for penalty in (0., .25):
                    for strength in (0., .05):
                        trial = {**model, 'closure_penalty': penalty, 'transition_strength': strength}
                        stats = summary(dev, [decode(trial, probability) for probability in native])
                        passes = eligible(stats, gate)
                        key = passes, stats['f1'], stats['agreement']
                        candidates.append({'arm': arm, 'epoch': epoch, 'penalty': penalty,
                                           'transition': strength, 'eligible': passes, **stats})
                        if best_key is None or key > best_key:
                            best, best_key = copy.deepcopy(trial), key
                print(json.dumps({'language':language, 'arm':arm, 'epoch':epoch, 'loss':network.loss_,
                                  'best_dev':best_key}), flush=True)
            selected_arms[arm] = (best, best_key)
            (args.output/f'{arm}-{language}.json').write_text(json.dumps(best), encoding='utf8')
            del network, x, y, w; gc.collect()
        winner, selected_key = max(selected_arms.values(), key=lambda pair:pair[1])
        # Freeze all models and decoder choices before inspecting any fresh test outcome.
        (args.output/f'hybrid-{language}.json').write_text(json.dumps(winner), encoding='utf8')
        results = {}
        for name, model in [('xgboost',baseline), ('forest',forest),
                            *[(name, pair[0]) for name,pair in selected_arms.items()]]:
            result, predictions = evaluate(test, model)
            results[name] = result
            if model is winner:
                for row, prediction in zip(test,predictions):
                    (args.output/f"prediction-{row['id']}.json").write_text(json.dumps(timeline(prediction,row['hop'],row['duration'])))
        report['languages'][language] = {'train':len(train), 'dev':len(dev), 'test':len(test),
            'test_groups':len({r['group_id'] for r in test}), 'selection':{k:winner[k] for k in
                ('arm','epoch','closure_penalty','transition_strength')},
            'dev_guardrails_passed':bool(selected_key[0]), 'dev_baseline':gate, 'candidates':candidates,
            'results':results, 'boosted':results[winner['arm']], 'identity':results['forest'],
            'model_names': {'boosted':'Small TDNN', 'identity':'Random Forest'}}
        (args.output/'evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({'language':language,'selected':winner['arm'], 'test':{
            name:r['grouped_advice'] for name,r in results.items()}}),flush=True)
        for row in subset:
            for key in ('identity_features','phonetic_features','timing_features'):
                row.pop(key,None)
        del values, train_context, dev_values, dev_context, subset, train, dev, test; gc.collect()


if __name__ == '__main__':
    main()
