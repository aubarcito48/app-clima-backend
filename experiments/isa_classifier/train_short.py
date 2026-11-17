"""Short app-style narration; choose models by novel advice, excluding repeated greetings."""

import argparse
import json
from pathlib import Path

import numpy as np

from classifier import timeline
from narration import app_text, advice_spans
from train_temporal import load_corpus
from train_next import choose, evaluate


def core_mask(row):
    count = len(row['labels'])
    times = np.minimum((np.arange(count) + .5) * row['hop'], row['duration'] - 1e-9)
    mask = np.zeros(count, dtype=bool)
    for start, end in row['advice_spans']:
        mask |= (times >= start) & (times < end)
    if not mask.any():
        raise ValueError('No advice windows found')
    return mask


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--previous-corpus', action='append', type=Path, required=True)
    parser.add_argument('--reference-v3', type=Path, required=True)
    parser.add_argument('--reference-v5', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows, manifest = load_corpus(args.corpus)
    if manifest.get('narration_profile') != 'app-greeting-v1':
        parser.error('Use the app narration profile with greeting and farewell')
    known, hashes = set(), set()
    for corpus in args.previous_corpus:
        for row in json.loads(corpus.read_text(encoding='utf8'))['recordings']:
            known.add((row['language'], ' '.join(row.get('advice', row['text']).casefold().split())))
            hashes.add(row['sha256_pcm'])
    for row in rows:
        if row['text'] != app_text(row['advice'], row['language']):
            parser.error('Greeting or farewell differs from app narration')
        if row['split'] != 'train' and ((row['language'], ' '.join(row['advice'].casefold().split())) in known
                                        or row['sha256_pcm'] in hashes):
            parser.error('Reserved advice was already seen')
        actual_spans = advice_spans((args.corpus.parent / row['file']).read_bytes(), row['duration'])
        if actual_spans != row['advice_spans']:
            parser.error('Advice spans differ from real synthesis timings')
        row['advice_mask'] = core_mask(row)
        # Keep learning the required greeting/farewell, but give novel advice
        # four times their loss weight. This rule is fixed before evaluation.
        row['loss_weights'] = np.where(row['advice_mask'], 1., .25)
    args.output.mkdir(parents=True, exist_ok=True)
    report = {'status': 'experimental_not_for_production', 'reference': manifest['reference'],
              'plan_sha256': manifest['plan_sha256'], 'narration_profile': manifest['narration_profile'],
              'selection': '24 fixed candidates; development advice-only pooled macro F1, then advice agreement',
              'warning': 'Repeated greeting/farewell excluded from primary metrics; full narration is secondary',
              'training_focus': 'advice loss 1.0; greeting/farewell loss 0.25, then mean-normalized',
              'languages': {}}
    for language in ('es', 'en'):
        train = [r for r in rows if r['language'] == language and r['split'] == 'train']
        dev = [r for r in rows if r['language'] == language and r['split'] == 'dev']
        test = [r for r in rows if r['language'] == language and r['split'] == 'test']
        winner, _, candidates = choose(train, dev, advice_only=True)
        model = winner[2]
        model.update(language=language, modality='audio', reference=manifest['reference'], narration_profile='app-greeting-v1',
                     training=[{'file': r['file'], 'sha256_pcm': r['sha256_pcm']} for r in train])
        (args.output / f'audio-{language}.json').write_text(json.dumps(model, indent=2), encoding='utf8')
        controls = {'selected_v6': model,
            'frozen_v3': json.loads((args.reference_v3 / f'audio-{language}.json').read_text()),
            'frozen_v5': json.loads((args.reference_v5 / f'audio-{language}.json').read_text())}
        results = {}
        for name, candidate in controls.items():
            full, predictions = evaluate(test, candidate)
            core, _ = evaluate(test, candidate, advice_only=True)
            results[name] = {'advice_only': core, 'full_narration': full}
            if name == 'selected_v6':
                for index, (row, predicted) in enumerate(zip(test, predictions)):
                    (args.output / f'prediction-{language}-{index}.json').write_text(json.dumps({
                        'mouthCues': timeline(predicted, row['hop'], row['duration'])}, indent=2), encoding='utf8')
        report['languages'][language] = {'train_recordings': len(train), 'dev_recordings': len(dev), 'test_recordings': len(test),
            'selected': {'nonlinear_scale': winner[3], **{k: model[k] for k in ('ridge', 'balance', 'transition_strength')}},
            'training_counts': model['counts'], 'model_bytes': (args.output / f'audio-{language}.json').stat().st_size,
            'development': [{'scale': c[3], 'ridge': c[2]['ridge'], 'balance': c[2]['balance'],
                             'transition_strength': c[2]['transition_strength'], 'advice_macro_f1': c[0],
                             'advice_agreement': c[1]} for c in candidates], 'test': results}
        print(json.dumps({'language': language, 'advice_only': {name: {
            'agreement': r['advice_only']['mean_recording_agreement'], 'macro_f1': r['advice_only']['pooled']['macro_f1']}
            for name, r in results.items()}}), flush=True)
    (args.output / 'evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
