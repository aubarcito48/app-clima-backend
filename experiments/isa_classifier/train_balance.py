"""Fixed balancing study: select on new development data, test selected models once."""

import argparse
import copy
import json
from pathlib import Path

import numpy as np

import temporal
from classifier import metrics, timeline
from train_temporal import load_corpus, score

BALANCES = (0., .25, .5, .75, 1.)


def select_balance(train, dev):
    by_balance = []
    for balance in BALANCES:
        candidates = []
        for ridge in (1., 100.):
            model = temporal.fit(train, ridge=ridge, balance=balance, weight_cap=4.)
            for strength in (0., .05, .15):
                model['transition_strength'] = strength
                predictions = [temporal.predict(model, r['features']) for r in dev]
                result = score(dev, predictions)
                pooled = metrics(np.concatenate([r['labels'] for r in dev]), np.concatenate(predictions))
                result['pooled'] = pooled
                candidates.append((pooled['macro_f1'], result['mean_recording_agreement'],
                                   copy.deepcopy(model), result))
        by_balance.append(max(candidates, key=lambda item: item[:2]))
    winner = max(by_balance, key=lambda item: item[:2])
    return winner, by_balance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--previous-corpus', type=Path, required=True)
    parser.add_argument('--previous-models', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows, manifest = load_corpus(args.corpus)
    previous = json.loads(args.previous_corpus.read_text(encoding='utf8'))
    prior_texts = {(r['language'], ' '.join(r['text'].casefold().split())) for r in previous['recordings']}
    prior_hashes = {r['sha256_pcm'] for r in previous['recordings']}
    for row in rows:
        if row['split'] != 'train' and ((row['language'], ' '.join(row['text'].casefold().split())) in prior_texts
                                        or row['sha256_pcm'] in prior_hashes):
            parser.error('Development/test must be new relative to the previous round')
    args.output.mkdir(parents=True, exist_ok=True)
    report = {'status': 'experimental_not_for_production', 'reference': manifest['reference'],
              'plan_sha256': manifest['plan_sha256'], 'balances': BALANCES, 'weight_cap_before_normalization': 4.,
              'selection': '30 fixed candidates/language; development pooled macro F1, agreement tie break',
              'test_policy': 'only development winner, unbalanced development winner and frozen V3 control',
              'languages': {}}
    for language in ('es', 'en'):
        train = [r for r in rows if r['language'] == language and r['split'] == 'train']
        dev = [r for r in rows if r['language'] == language and r['split'] == 'dev']
        test = [r for r in rows if r['language'] == language and r['split'] == 'test']
        winner, study = select_balance(train, dev)
        model = winner[2]
        model.update(language=language, modality='audio', reference=manifest['reference'],
                     training=[{'file': r['file'], 'sha256_pcm': r['sha256_pcm']} for r in train])
        (args.output / f'audio-{language}.json').write_text(json.dumps(model, indent=2), encoding='utf8')
        frozen = json.loads((args.previous_models / f'audio-{language}.json').read_text(encoding='utf8'))
        controls = {'selected': model, 'unbalanced': study[0][2], 'frozen_v3': frozen}
        results = {}
        for name, candidate in controls.items():
            predictions = [temporal.predict(candidate, r['features']) for r in test]
            results[name] = score(test, predictions)
            results[name]['pooled'] = metrics(np.concatenate([r['labels'] for r in test]), np.concatenate(predictions))
            if name == 'selected':
                for index, (row, predicted) in enumerate(zip(test, predictions)):
                    (args.output / f'prediction-{language}-{index}.json').write_text(json.dumps({
                        'mouthCues': timeline(predicted, row['hop'], row['duration'])}, indent=2), encoding='utf8')
        confusion = results['selected']['pooled']['confusion']
        errors = sorted([{'actual': a, 'predicted': b, 'windows': n} for a, column in confusion.items()
                          for b, n in column.items() if a != b and n], key=lambda r: -r['windows'])
        report['languages'][language] = {
            'train_recordings': len(train), 'dev_recordings': len(dev), 'test_recordings': len(test),
            'training_counts': model['counts'], 'selected': {k: model[k] for k in (
                'ridge', 'balance', 'weight_cap', 'weight_range', 'transition_strength')},
            'development_balance_study': [{'balance': r[2]['balance'], 'macro_f1': r[0],
                'agreement': r[1], 'balanced_recall': r[3]['pooled']['balanced_recall']}
                for r in study],
            'test': results, 'largest_confusions': errors[:12]}
        print(json.dumps({'language': language, 'selected_balance': model['balance'],
            'results': {name: {'agreement': r['mean_recording_agreement'],
                              'macro_f1': r['pooled']['macro_f1']} for name, r in results.items()}}), flush=True)
    (args.output / 'evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
