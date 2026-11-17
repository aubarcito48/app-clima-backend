"""Select on development recordings, then evaluate on frozen unseen test files."""

import argparse
import copy
import json
from pathlib import Path
import time

import numpy as np

import temporal
from classifier import audio_features, classify, fit, labels_at, metrics, read_recording, smooth, timeline
from generate_corpus import validate_plan


def score(rows, predictions):
    reports = [metrics(row['labels'], predicted) for row, predicted in zip(rows, predictions)]
    return {'mean_recording_agreement': float(np.mean([r['frame_agreement'] for r in reports])),
            'mean_recording_macro_f1': float(np.mean([r['macro_f1'] for r in reports])),
            'mean_recording_balanced_recall': float(np.mean([r['balanced_recall'] for r in reports])),
            'recordings': [{'file': row['file'], **result} for row, result in zip(rows, reports)]}


def load_corpus(path):
    manifest = json.loads(path.read_text(encoding='utf8'))
    validate_plan(manifest)
    rows, seen = [], set()
    for row in manifest['recordings']:
        file = path.parent / row['file']
        if file.resolve().parent != path.parent.resolve():
            raise ValueError('Corpus files must stay inside the manifest directory')
        samples, rate, cues, fingerprint = read_recording(file)
        if fingerprint != row['sha256_pcm'] or fingerprint in seen:
            raise ValueError('Changed or duplicate PCM in corpus')
        seen.add(fingerprint)
        features, times, hop = audio_features(samples, rate)
        labels = labels_at(cues, times, len(samples) / rate)
        rows.append({**row, 'features': features, 'labels': labels, 'hop': hop})
    return rows, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows, manifest = load_corpus(args.corpus)
    args.output.mkdir(parents=True, exist_ok=True)
    report = {'status': 'experimental_not_for_production', 'reference': manifest['reference'],
              'plan_sha256': manifest['plan_sha256'],
              'selection': '12 fixed candidates, development macro recall then agreement; test excluded',
              'languages': {}}
    for language in ('es', 'en'):
        train = [r for r in rows if r['language'] == language and r['split'] == 'train']
        dev = [r for r in rows if r['language'] == language and r['split'] == 'dev']
        test = [r for r in rows if r['language'] == language and r['split'] == 'test']
        candidates = []
        for ridge in (1., 100.):
            for balance in (0., .5):
                model = temporal.fit(train, ridge=ridge, balance=balance)
                for strength in (0., .05, .15):
                    model['transition_strength'] = strength
                    result = score(dev, [temporal.predict(model, r['features']) for r in dev])
                    candidates.append((result['mean_recording_balanced_recall'],
                                       result['mean_recording_agreement'], copy.deepcopy(model), result))
        _, _, best, dev_result = max(candidates, key=lambda item: item[:2])
        best.update(language=language, modality='audio', reference=manifest['reference'],
                    training=[{'file': r['file'], 'sha256_pcm': r['sha256_pcm']} for r in train])
        (args.output / f'audio-{language}.json').write_text(json.dumps(best, indent=2), encoding='utf8')
        centroid = fit(np.concatenate([r['features'] for r in train]), np.concatenate([r['labels'] for r in train]))
        majority = max(centroid['counts'], key=centroid['counts'].get)
        started = time.perf_counter()
        predictions = [temporal.predict(best, r['features']) for r in test]
        elapsed = time.perf_counter() - started
        evaluation = score(test, predictions)
        baseline = score(test, [smooth(classify(centroid, r['features'])[0]) for r in test])
        trivial = score(test, [np.full(len(r['labels']), majority) for r in test])
        for index, (row, predicted) in enumerate(zip(test, predictions)):
            (args.output / f'prediction-{language}-{index}.json').write_text(json.dumps({
                'mouthCues': timeline(predicted, row['hop'], row['duration'])}, indent=2), encoding='utf8')
        result = {'train_recordings': len(train), 'dev_recordings': len(dev), 'test_recordings': len(test),
                  'missing_training_shapes': sorted(set('ABCDEFGHX') - set(best['classes'])),
                  'selected': {k: best[k] for k in ('ridge', 'balance', 'transition_strength')},
                  'development': dev_result, 'temporal_test': evaluation,
                  'centroid_same_corpus_test': baseline, 'majority_test': trivial,
                  'test_decoding_seconds': elapsed, 'model_bytes': (args.output / f'audio-{language}.json').stat().st_size}
        report['languages'][language] = result
        print(json.dumps({'language': language, 'temporal': evaluation['mean_recording_agreement'],
                          'centroid': baseline['mean_recording_agreement'], 'majority': trivial['mean_recording_agreement'],
                          'balanced_recall': evaluation['mean_recording_balanced_recall']}), flush=True)
    (args.output / 'evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
