"""Fixed dev-only hybrid training; test is split-preserving V7 phrase reevaluation."""
import os
for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'
import argparse
import copy
import json
from pathlib import Path
import numpy as np
import temporal
from classifier import read_recording, labels_at, metrics, timeline
from narration import advice_spans, performance_rows
from phonetic_features import PROFILE, hybrid_features
from rhythm_features import timing_features
from train_temporal import load_corpus, score
from train_short import core_mask
from train_rhythm import measure


def grouped_advice_score(rows, predictions):
    groups = {}
    for row, predicted in zip(rows, predictions):
        key = row.get('group_id', row['id'])
        expected, actual = groups.setdefault(key, ([], []))
        expected.append(row['labels'][row['advice_mask']])
        actual.append(predicted[row['advice_mask']])
    results = {key: metrics(np.concatenate(a), np.concatenate(b)) for key, (a, b) in groups.items()}
    return {'phrase_groups': len(results),
            'mean_group_agreement': float(np.mean([r['frame_agreement'] for r in results.values()])),
            'mean_group_macro_f1': float(np.mean([r['macro_f1'] for r in results.values()])), 'groups': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rate-expansion', action='store_true')
    parser.add_argument('--reference-hybrid', type=Path)
    parser.add_argument('--phoneme-identity', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows, manifest = load_corpus(args.corpus)
    vocabularies = {}
    if args.phoneme_identity:
        from phoneme_identity import vocabulary_from_training, identity_features, PROFILE as IDENTITY_PROFILE
        for language in ('es', 'en'):
            alignments = [json.loads((args.corpus.parent / row['phones_file']).read_text(encoding='utf8'))
                          for row in rows if row['language'] == language and row['split'] == 'train']
            vocabularies[language] = vocabulary_from_training(alignments)
    if args.rate_expansion:
        groups = {}
        for row in rows:
            identity = (row['language'], row.get('group_id'))
            value = (row['split'], row['text'])
            if not identity[1] or identity in groups and groups[identity] != value:
                raise ValueError('Rate variants crossed groups or splits')
            groups[identity] = value
    for row in rows:
        wav = args.corpus.parent / row['file']
        samples, rate, _, _ = read_recording(wav)
        if advice_spans(wav.read_bytes(), row['duration']) != row['advice_spans']:
            raise ValueError('Changed advice spans')
        info = json.loads((args.corpus.parent / row['phones_file']).read_text(encoding='utf8'))
        raw_path = (args.corpus.parent / row['phones_file']).parent / f"raw-{row['language']}.wav"
        if read_recording(raw_path)[3] != row['sha256_pcm']:
            raise ValueError('Alignment source PCM differs from training WAV')
        info['sha256_pcm'] = row['sha256_pcm']
        if info['text'] != row['text']:
            raise ValueError('Changed phonetic narration')
        row['phonetic_features'], times, _ = hybrid_features(samples, rate, info)
        if args.phoneme_identity:
            row['identity_features'], _, _ = identity_features(samples, rate, info, vocabularies[row['language']])
            row['identity_vocabulary'] = vocabularies[row['language']]
        row['timing_features'], _, _ = timing_features(samples, rate)
        row['phonetic_labels'] = labels_at(info['cues'], times, row['duration'])
        row['advice_mask'] = core_mask(row)
        row['known_pause_mask'] = np.zeros(len(times), dtype=bool)
        for segment in performance_rows(wav.read_bytes(), row['duration']):
            row['known_pause_mask'] |= (times >= segment['speech_end']) & (times < segment['until'])
        row['loss_weights'] = np.where(row['advice_mask'], 1., .25)
        if args.rate_expansion and row['split'] == 'train':
            copies = sum(r['split'] == 'train' and r['language'] == row['language']
                         and r.get('group_id') == row.get('group_id') for r in rows)
            row['loss_weights'] /= copies
    report = {'reference': 'weak-rhubarb-not-human-gold', 'status': 'local_experiment',
              'test_warning': manifest['warning'], 'plan_sha256': manifest['plan_sha256'],
              'selection': f'{16 if args.rate_expansion else 8} fixed candidates/language; advice dev macro F1 then agreement', 'languages': {}}
    for language in ('es', 'en'):
        subset = [r for r in rows if r['language'] == language]
        train = [{**r, 'features': r['identity_features' if args.phoneme_identity else 'phonetic_features']}
                 for r in subset if r['split'] == 'train']
        dev = [r for r in subset if r['split'] == 'dev']
        test = [r for r in subset if r['split'] == 'test' and (not args.rate_expansion or r.get('evaluation') == 'fresh')]
        candidates = []
        for balance in ((.25, .5) if args.rate_expansion else (.5,)):
          for nonlinear in (None, .5):
            for ridge in (1., 100.):
                model = temporal.fit(train, ridge=ridge, balance=balance, weight_cap=4., nonlinear_scale=nonlinear)
                model['feature_profile'] = IDENTITY_PROFILE if args.phoneme_identity else PROFILE
                if args.phoneme_identity:
                    model['phoneme_vocabulary'] = vocabularies[language]
                for strength in (0., .05):
                    model['transition_strength'] = strength
                    result, dev_predictions = measure(dev, model)
                    core = result['advice_only']
                    if args.rate_expansion:
                        grouped = grouped_advice_score(dev, dev_predictions)
                        candidates.append((grouped['mean_group_macro_f1'], grouped['mean_group_agreement'], copy.deepcopy(model)))
                    else:
                        candidates.append((core['pooled']['macro_f1'], core['mean_recording_agreement'], copy.deepcopy(model)))
        best = max(candidates, key=lambda c: c[:2])[2]
        best.update(language=language, modality='audio-plus-synthesis-phonemes',
                    training=[{'file': r['file'], 'sha256_pcm': r['sha256_pcm']} for r in train])
        (args.output / f'hybrid-{language}.json').write_text(json.dumps(best), encoding='utf8')
        selected, predictions = measure(test, best)
        baseline = json.loads((args.baseline / f'audio-{language}.json').read_text())
        previous, baseline_predictions = measure(test, baseline)
        prior_hybrid = None
        if args.reference_hybrid:
            frozen = json.loads((args.reference_hybrid / f'hybrid-{language}.json').read_text())
            prior_hybrid, prior_predictions = measure(test, frozen)
        if args.rate_expansion:
            selected['grouped_advice'] = grouped_advice_score(test, predictions)
            previous['grouped_advice'] = grouped_advice_score(test, baseline_predictions)
            if prior_hybrid:
                prior_hybrid['grouped_advice'] = grouped_advice_score(test, prior_predictions)
        raw_rows = [{**r, 'labels': r['labels'][r['advice_mask']]} for r in test]
        raw_predictions = [r['phonetic_labels'][r['advice_mask']] for r in test]
        raw = score(raw_rows, raw_predictions)
        raw['pooled'] = metrics(np.concatenate([r['labels'] for r in raw_rows]), np.concatenate(raw_predictions))
        for row, prediction in zip(test, predictions):
            (args.output / f"prediction-{row['id']}.json").write_text(json.dumps(timeline(prediction, row['hop'], row['duration'])))
        report['languages'][language] = {'train': len(train), 'dev': len(dev), 'test': len(test),
            'test_phrase_groups': len({r.get('group_id', r['id']) for r in test}),
            'training_counts': best['counts'], 'previous_hybrid': prior_hybrid,
            'selection': {k: best[k] for k in ('ridge', 'balance', 'transition_strength', 'feature_profile')},
            'development': [{'macro_f1': c[0], 'agreement': c[1], 'ridge': c[2]['ridge'],
                             'balance': c[2]['balance'],
                             'nonlinear': bool(c[2].get('nonlinear')), 'transition_strength': c[2]['transition_strength']} for c in candidates],
            'hybrid': selected, 'v7': previous, 'raw_phonetic_advice': raw}
        if args.rate_expansion:
            breakdown = {}
            for variant in ('baseline', 'automatic'):
                variant_rows = [r for r in test if r['variant'] == variant]
                if variant_rows:
                    breakdown[variant] = {'recordings': len(variant_rows),
                        'new_hybrid': measure(variant_rows, best)[0], 'v7': measure(variant_rows, baseline)[0],
                        'previous_hybrid': measure(variant_rows, frozen)[0] if args.reference_hybrid else None}
            report['languages'][language]['test_by_rate_variant'] = breakdown
        print(json.dumps({'language': language, 'advice': {name: {'agreement': result['mean_recording_agreement'],
            'macro_f1': result['pooled']['macro_f1']} for name, result in
            [('hybrid', selected['advice_only']), ('v7', previous['advice_only']), ('raw_phones', raw)]}}), flush=True)
    (args.output / 'evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
