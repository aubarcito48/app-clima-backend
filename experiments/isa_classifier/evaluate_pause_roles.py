"""Report advice/greeting pause performance without changing model predictions."""
import argparse
import json
from pathlib import Path
import numpy as np
import temporal
from classifier import read_recording
from narration import performance_rows
from pause_labels import verified_intervals, pause_masks
from rhythm_features import features_for_model


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--corpus', type=Path, required=True)
    p.add_argument('--new', type=Path, required=True)
    p.add_argument('--previous', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    manifest = json.loads(args.corpus.read_text(encoding='utf8'))
    totals = {}
    for row in manifest['recordings']:
        if row['split'] != 'test' or row.get('evaluation') != 'fresh':
            continue
        wav = args.corpus.parent / row['file']
        samples, rate, _, fingerprint = read_recording(wav)
        if fingerprint != row['sha256_pcm']:
            raise ValueError('Evaluation PCM changed')
        info = json.loads((args.corpus.parent / row['phones_file']).read_text(encoding='utf8'))
        info['sha256_pcm'] = fingerprint
        performance = performance_rows(wav.read_bytes(), row['duration'])
        intervals = verified_intervals(samples, rate, performance, info['phonemes'])
        for name, folder in [('new', args.new), ('previous', args.previous)]:
            model = json.loads((folder / f"hybrid-{row['language']}.json").read_text())
            features, times, _ = features_for_model(model, samples, rate, alignment=info)
            predicted = temporal.predict(model, features)
            full, safe = pause_masks(intervals, len(times), rate, times)
            advice = np.zeros(len(times), dtype=bool)
            for segment in performance[1:-1]:
                advice |= (times >= segment['from']) & (times < segment['until'])
            greeting = (times >= performance[0]['from']) & (times < performance[0]['until'])
            for role, mask in [('advice_interior', safe & advice), ('greeting_interior', safe & greeting), ('advice_all_pause', full & advice)]:
                key = f"{row['language']}-{name}-{role}"
                result = totals.setdefault(key, {'windows': 0, 'closed': 0, 'rest_x': 0})
                values = predicted[mask]
                result['windows'] += len(values)
                result['closed'] += int(np.isin(values, ['A', 'X']).sum())
                result['rest_x'] += int((values == 'X').sum())
    for result in totals.values():
        result['closed_rate'] = result['closed']/result['windows'] if result['windows'] else None
    args.output.write_text(json.dumps(totals, indent=2))
    print(json.dumps(totals))


if __name__ == '__main__':
    main()
