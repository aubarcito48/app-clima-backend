"""V5: expanded corpus and a small nonlinear feature model; fixed dev-only search."""

import argparse
import copy
import json
from pathlib import Path
import time

import numpy as np

from classifier import metrics, timeline
from train_temporal import load_corpus, score
import temporal
from rhythm_features import row_features


def evaluate(rows, model, *, advice_only=False):
    predictions = [temporal.predict(model, row_features(model, r)) for r in rows]
    if advice_only:
        selected_rows, selected_predictions = [], []
        for row, predicted in zip(rows, predictions):
            mask = row.get('advice_mask')
            if mask is None or len(mask) != len(predicted) or not np.asarray(mask).any():
                raise ValueError('Advice-only evaluation needs verified performance spans')
            selected_rows.append({**row, 'labels': row['labels'][mask]})
            selected_predictions.append(predicted[mask])
        rows, predictions = selected_rows, selected_predictions
    report = score(rows, predictions)
    report['pooled'] = metrics(np.concatenate([r['labels'] for r in rows]), np.concatenate(predictions))
    return report, predictions


def choose(train, dev, *, advice_only=False):
    candidates = []
    for nonlinear in (None, .5, 1.5):
        for balance in (.25, .5):
            for ridge in (1., 100.):
                model = temporal.fit(train, ridge=ridge, balance=balance, weight_cap=4., nonlinear_scale=nonlinear)
                for strength in (0., .05):
                    model['transition_strength'] = strength
                    report, _ = evaluate(dev, model, advice_only=advice_only)
                    candidates.append((report['pooled']['macro_f1'], report['mean_recording_agreement'],
                                       copy.deepcopy(model), nonlinear, report))
    return max(candidates, key=lambda c: c[:2]), max(
        [c for c in candidates if c[3] is None], key=lambda c: c[:2]), candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--previous-corpus', type=Path, action='append', required=True)
    parser.add_argument('--reference-models', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows, manifest = load_corpus(args.corpus)
    known_texts, known_hashes = set(), set()
    for path in args.previous_corpus:
        for row in json.loads(path.read_text(encoding='utf8'))['recordings']:
            known_texts.add((row['language'], ' '.join(row['text'].casefold().split())))
            known_hashes.add(row['sha256_pcm'])
    for row in rows:
        if row['split'] != 'train' and ((row['language'], ' '.join(row['text'].casefold().split())) in known_texts
                                        or row['sha256_pcm'] in known_hashes):
            parser.error('Development/test data already appeared in an earlier round')
    args.output.mkdir(parents=True, exist_ok=True)
    report = {'status': 'experimental_not_for_production', 'reference': manifest['reference'],
              'plan_sha256': manifest['plan_sha256'], 'selection': '24 fixed candidates/language; development pooled macro F1 then agreement',
              'languages': {}}
    for language in ('es', 'en'):
        train = [r for r in rows if r['language'] == language and r['split'] == 'train']
        dev = [r for r in rows if r['language'] == language and r['split'] == 'dev']
        test = [r for r in rows if r['language'] == language and r['split'] == 'test']
        winner, linear, candidates = choose(train, dev)
        model = winner[2]
        model.update(language=language, modality='audio', reference=manifest['reference'],
                     training=[{'file': r['file'], 'sha256_pcm': r['sha256_pcm']} for r in train])
        (args.output / f'audio-{language}.json').write_text(json.dumps(model, indent=2), encoding='utf8')
        frozen = json.loads((args.reference_models / f'audio-{language}.json').read_text(encoding='utf8'))
        results = {}
        for name, candidate in [('selected', model), ('expanded_linear', linear[2]), ('frozen_v3', frozen)]:
            started = time.perf_counter()
            result, predictions = evaluate(test, candidate)
            result['prediction_and_scoring_seconds'] = time.perf_counter() - started
            results[name] = result
            if name == 'selected':
                for index, (row, predicted) in enumerate(zip(test, predictions)):
                    (args.output / f'prediction-{language}-{index}.json').write_text(json.dumps({
                        'mouthCues': timeline(predicted, row['hop'], row['duration'])}, indent=2), encoding='utf8')
        report['languages'][language] = {'train_recordings': len(train), 'dev_recordings': len(dev), 'test_recordings': len(test),
            'selected': {'nonlinear_scale': winner[3], **{k: model[k] for k in ('version', 'ridge', 'balance', 'transition_strength')}},
            'training_counts': model['counts'], 'model_bytes': (args.output / f'audio-{language}.json').stat().st_size,
            'development': [{'nonlinear_scale': c[3], 'ridge': c[2]['ridge'], 'balance': c[2]['balance'],
                              'transition_strength': c[2]['transition_strength'], 'macro_f1': c[0], 'agreement': c[1]}
                             for c in candidates], 'test': results}
        print(json.dumps({'language': language, 'nonlinear_scale': winner[3], 'test': {
            name: {'agreement': r['mean_recording_agreement'], 'macro_f1': r['pooled']['macro_f1']}
            for name, r in results.items()}}), flush=True)
    (args.output / 'evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
