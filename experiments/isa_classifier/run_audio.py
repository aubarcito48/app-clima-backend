"""Train/evaluate independent ES/EN baselines using existing local labelled WAVs."""

import argparse
import json
from pathlib import Path

import numpy as np

from classifier import audio_features, classify, fit, labels_at, metrics, read_recording, smooth, timeline
from annotations import read_annotations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--train', action='append', required=True, help='es:path.wav or en:path.wav')
    parser.add_argument('--test', action='append', required=True, help='Independent held-out recording')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--annotations-dir', type=Path, help='Reviewed sidecars named like each WAV stem + .json')
    parser.add_argument('--require-reviewed', action='store_true', help='Reject every unreviewed recording')
    args = parser.parse_args()
    datasets = {'train': [], 'test': []}
    seen = set()
    for split, entries in (('train', args.train), ('test', args.test)):
        for entry in entries:
            language, path = entry.split(':', 1)
            if language not in {'es', 'en'}:
                parser.error('Language must be es or en')
            samples, rate, cues, fingerprint = read_recording(path)
            label_source = 'weak-rhubarb'
            sidecar = args.annotations_dir / (Path(path).stem + '.json') if args.annotations_dir else None
            if sidecar and sidecar.is_file():
                cues = read_annotations(sidecar, fingerprint, language, len(samples) / rate)
                label_source = 'human-reviewed'
            elif args.require_reviewed:
                parser.error(f'Missing reviewed annotations for {Path(path).name}')
            if fingerprint in seen:
                parser.error('Duplicate PCM found: keep recordings independent')
            seen.add(fingerprint)
            features, times, hop = audio_features(samples, rate)
            labels = labels_at(cues, times, len(samples) / rate)
            datasets[split].append({'language': language, 'name': Path(path).name,
                                    'sha256_pcm': fingerprint, 'features': features,
                                    'label_source': label_source,
                                    'labels': labels, 'hop': hop, 'duration': len(samples) / rate})
    args.output.mkdir(parents=True, exist_ok=True)
    report = {'status': 'experimental_not_for_production',
              'reference': 'per-recording label_source distinguishes weak and human-reviewed labels',
              'split_unit': 'whole recording; exact PCM deduplicated; review text overlap manually',
              'languages': {}}
    for language in ('es', 'en'):
        training = [r for r in datasets['train'] if r['language'] == language]
        testing = [r for r in datasets['test'] if r['language'] == language]
        if not training or not testing:
            parser.error(f'Both train and test are required for {language}')
        model = fit(np.concatenate([r['features'] for r in training]),
                    np.concatenate([r['labels'] for r in training]))
        model.update(language=language, modality='audio',
                     training=[{'file': r['name'], 'sha256_pcm': r['sha256_pcm'],
                                'label_source': r['label_source']} for r in training])
        (args.output / f'audio-{language}.json').write_text(json.dumps(model, indent=2), encoding='utf8')
        results = []
        majority = max(model['counts'], key=model['counts'].get)
        for index, row in enumerate(testing):
            # Inference reads acoustic features only. Reference labels are used
            # below solely to score the already produced predictions.
            predicted, _ = classify(model, row['features'])
            predicted = smooth(predicted)
            cues = timeline(predicted, row['hop'], row['duration'])
            (args.output / f'prediction-{language}-{index}.json').write_text(
                json.dumps({'mouthCues': cues}, indent=2), encoding='utf8')
            results.append({'file': row['name'], 'sha256_pcm': row['sha256_pcm'],
                            'label_source': row['label_source'],
                            'duration': row['duration'], 'cues': len(cues),
                            'training_majority_shape': majority,
                            'majority_baseline_agreement': float(np.mean(row['labels'] == majority)),
                            **metrics(row['labels'], predicted)})
        report['languages'][language] = {'training_recordings': len(training),
                                         'missing_training_shapes': sorted(set('ABCDEFGHX') - set(model['classes'])),
                                         'evaluation': results}
    target = args.output / 'evaluation.json'
    target.write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps({'report': str(target), 'results': {lang: [
        {'file': r['file'], 'agreement': round(r['frame_agreement'], 3),
         'balanced_recall': round(r['balanced_recall'], 3)} for r in data['evaluation']]
        for lang, data in report['languages'].items()}}))


if __name__ == '__main__':
    main()
