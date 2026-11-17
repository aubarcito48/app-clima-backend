"""Prepare frozen hybrid predictions and independent weak references by split."""
import argparse
import json
from pathlib import Path
import temporal
from classifier import read_recording, timeline
from analyze_timing import analyze
from rhythm_features import features_for_model
from pause_labels import verified_intervals
from narration import performance_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--models', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--fresh-test-only', action='store_true')
    parser.add_argument('--verified-pauses', action='store_true')
    args = parser.parse_args()
    manifest = json.loads(args.corpus.read_text(encoding='utf8'))
    models = {lang: json.loads((args.models / f'hybrid-{lang}.json').read_text()) for lang in ('es', 'en')}
    references = {lang: json.loads((args.reference / f'hybrid-{lang}.json').read_text()) for lang in ('es', 'en')} if args.reference else None
    rows = []
    for row in manifest['recordings']:
        if args.fresh_test_only and not (row['split'] == 'test' and row.get('evaluation') == 'fresh'):
            continue
        wav = args.corpus.parent / row['file']
        samples, rate, reference, fingerprint = read_recording(wav)
        if fingerprint != row['sha256_pcm']:
            raise ValueError('Corpus changed')
        info_path = args.corpus.parent / row['phones_file']
        info = json.loads(info_path.read_text(encoding='utf8'))
        if read_recording(info_path.parent / f"raw-{row['language']}.wav")[3] != fingerprint:
            raise ValueError('Phonetic source changed')
        info['sha256_pcm'] = fingerprint
        features, _, hop = features_for_model(models[row['language']], samples, rate, alignment=info)
        cues = timeline(temporal.predict(models[row['language']], features), hop, row['duration'])
        entry = {'id': row['id'], 'split': row['split'], 'language': row['language'],
                     'advice_spans': row['advice_spans'], 'sha256_pcm': fingerprint,
                     'reference': reference, 'cues': cues, 'timing': analyze(wav, row)}
        if args.verified_pauses:
            intervals = verified_intervals(samples, rate, performance_rows(wav.read_bytes(), row['duration']), info['phonemes'])
            entry['timing']['inserted_pauses'] = [{'start': p['start'], 'end': p['end'],
                'duration_ms': (p['end']-p['start'])*1000, 'kind': p['source'], 'verified': True} for p in intervals]
        if references:
            old = references[row['language']]
            old_features, _, old_hop = features_for_model(old, samples, rate, alignment=info)
            entry['versions'] = {'boosted': cues, 'previous': timeline(temporal.predict(old, old_features), old_hop, row['duration'])}
        rows.append(entry)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'batch.json').write_text(json.dumps({'source_plan_sha256': manifest['plan_sha256'],
        'warning': manifest['warning'], 'rows': rows}), encoding='utf8')
    if references:
        (args.output / 'visual-batch.json').write_text(json.dumps(rows), encoding='utf8')
    print(json.dumps({'recordings': len(rows), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
