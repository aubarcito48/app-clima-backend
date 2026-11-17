"""V7: enlarged corpus; compare acoustic vs PCM-derived timing channels on reserved advice."""

import argparse
import copy
import json
from pathlib import Path

import numpy as np

import temporal
from classifier import read_recording, timeline, metrics
from narration import app_text, advice_spans, performance_rows
from rhythm_features import PROFILE, timing_features
from train_temporal import load_corpus, score
from train_next import evaluate
from train_short import core_mask
from analyze_timing import analyze


def select(train, dev):
    candidates = []
    for profile in ('acoustic-v1', PROFILE):
        training = train if profile == 'acoustic-v1' else [{**r, 'features': r['timing_features']} for r in train]
        for scale in (None, .5, 1.5):
            for balance in (.25, .5):
                for ridge in (1., 100.):
                    model = temporal.fit(training, ridge=ridge, balance=balance, weight_cap=4., nonlinear_scale=scale)
                    model['feature_profile'] = profile
                    for strength in (0., .05):
                        model['transition_strength'] = strength
                        report, _ = evaluate(dev, model, advice_only=True)
                        candidates.append((report['pooled']['macro_f1'], report['mean_recording_agreement'],
                                           copy.deepcopy(model), scale))
    winner = max(candidates, key=lambda c: c[:2])
    base = max([c for c in candidates if c[2]['feature_profile'] == 'acoustic-v1'], key=lambda c: c[:2])
    return winner, base, candidates


def measure(rows, model):
    full, predictions = evaluate(rows, model)
    core_rows = [{**r, 'labels': r['labels'][r['advice_mask']]} for r in rows]
    core_pred = [p[r['advice_mask']] for r, p in zip(rows, predictions)]
    core = score(core_rows, core_pred)
    core['pooled'] = metrics(np.concatenate([r['labels'] for r in core_rows]), np.concatenate(core_pred))
    predicted = np.concatenate(core_pred)
    expected = np.concatenate([r['labels'] for r in core_rows])
    core['closed_while_reference_open_rate'] = float(np.mean(np.isin(predicted, ['A', 'X']) & ~np.isin(expected, ['A', 'X'])))
    pause_predictions = np.concatenate([p[r['known_pause_mask']] for r, p in zip(rows, predictions)])
    pauses = {'windows': len(pause_predictions), 'closed_rate': float(np.mean(np.isin(pause_predictions, ['A', 'X'])))
              if len(pause_predictions) else None,
              'reference': 'actual inserted Piper silence; independent of Rhubarb labels'}
    return {'advice_only': core, 'full_narration': full, 'known_pause_closure': pauses}, predictions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--previous-corpus', type=Path, action='append', required=True)
    parser.add_argument('--reference-v6', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows, manifest = load_corpus(args.corpus)
    if manifest.get('narration_profile') != 'app-greeting-v1':
        parser.error('App greeting/advice/farewell profile required')
    known, hashes = set(), set()
    for path in args.previous_corpus:
        for row in json.loads(path.read_text(encoding='utf8'))['recordings']:
            known.add((row['language'], ' '.join(row.get('advice', row['text']).casefold().split())))
            hashes.add(row['sha256_pcm'])
    for row in rows:
        if row['text'] != app_text(row['advice'], row['language']):
            parser.error('App narration changed')
        if row['split'] != 'train' and ((row['language'], ' '.join(row['advice'].casefold().split())) in known
                                        or row['sha256_pcm'] in hashes):
            parser.error('Previously observed advice in development/test')
        wav = args.corpus.parent / row['file']
        samples, rate, _, _ = read_recording(wav)
        if advice_spans(wav.read_bytes(), row['duration']) != row['advice_spans']:
            parser.error('Advice spans differ from real synthesis timings')
        row['advice_mask'] = core_mask(row)
        times = np.minimum((np.arange(len(row['labels'])) + .5) * row['hop'], row['duration'] - 1e-9)
        row['known_pause_mask'] = np.zeros(len(times), dtype=bool)
        for segment in performance_rows(wav.read_bytes(), row['duration']):
            row['known_pause_mask'] |= (times >= segment['speech_end']) & (times < segment['until'])
        row['loss_weights'] = np.where(row['advice_mask'], 1., .25)
        row['timing_features'], _, _ = timing_features(samples, rate)
    args.output.mkdir(parents=True, exist_ok=True)
    report = {'status': 'experimental_not_for_production', 'reference': manifest['reference'],
              'selection': '48 fixed candidates/language; development advice-only pooled macro F1 then agreement',
              'plan_sha256': manifest['plan_sha256'], 'languages': {}}
    visual = []
    for language in ('es', 'en'):
        train = [r for r in rows if r['language'] == language and r['split'] == 'train']
        dev = [r for r in rows if r['language'] == language and r['split'] == 'dev']
        test = [r for r in rows if r['language'] == language and r['split'] == 'test']
        winner, base, candidates = select(train, dev)
        model = winner[2]
        model.update(language=language, modality='audio', reference=manifest['reference'], narration_profile='app-greeting-v1',
                     training=[{'file': r['file'], 'sha256_pcm': r['sha256_pcm']} for r in train])
        (args.output / f'audio-{language}.json').write_text(json.dumps(model, indent=2), encoding='utf8')
        frozen = json.loads((args.reference_v6 / f'audio-{language}.json').read_text(encoding='utf8'))
        results = {}
        for name, candidate in [('selected_v7', model), ('expanded_base', base[2]), ('frozen_v6', frozen)]:
            result, predictions = measure(test, candidate)
            results[name] = result
            if name == 'selected_v7':
                for row, predicted in zip(test, predictions):
                    cues = timeline(predicted, row['hop'], row['duration'])
                    (args.output / f"prediction-{row['id']}.json").write_text(json.dumps({'mouthCues': cues}, indent=2), encoding='utf8')
                    visual.append({'id': row['id'], 'language': language, 'versions': {'selected_v7': cues},
                                   'timing': analyze(args.corpus.parent / row['file'], row)})
            elif name == 'frozen_v6':
                for row, predicted in zip(test, predictions):
                    entry = next(v for v in visual if v['id'] == row['id'])
                    entry['versions']['frozen_v6'] = timeline(predicted, row['hop'], row['duration'])
        a = results['selected_v7']['advice_only']['recordings']
        b = results['frozen_v6']['advice_only']['recordings']
        report['languages'][language] = {
            'train_recordings': len(train), 'dev_recordings': len(dev), 'test_recordings': len(test),
            'selected': {'feature_profile': model['feature_profile'], 'scale': winner[3],
                         **{k: model[k] for k in ('balance', 'ridge', 'transition_strength')}},
            'training_counts': model['counts'], 'model_bytes': (args.output / f'audio-{language}.json').stat().st_size,
            'development': [{'feature_profile': c[2]['feature_profile'], 'scale': c[3], 'balance': c[2]['balance'],
                             'ridge': c[2]['ridge'], 'transition_strength': c[2]['transition_strength'],
                             'advice_macro_f1': c[0], 'advice_agreement': c[1]} for c in candidates],
            'test': results, 'advice_agreement_wins_over_v6': sum(x['frame_agreement'] > y['frame_agreement'] for x, y in zip(a, b))}
        print(json.dumps({'language': language, 'features': model['feature_profile'], 'advice_only': {
            name: {'agreement': r['advice_only']['mean_recording_agreement'], 'macro_f1': r['advice_only']['pooled']['macro_f1']}
            for name, r in results.items()}}), flush=True)
    (args.output / 'evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    (args.output / 'visual-batch.json').write_text(json.dumps(visual), encoding='utf8')


if __name__ == '__main__':
    main()
