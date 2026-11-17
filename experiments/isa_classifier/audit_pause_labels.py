"""Read-only audit; originals remain unchanged; export a correction sidecar."""
import argparse
import json
from pathlib import Path
import numpy as np
from classifier import read_recording, audio_features, labels_at
from narration import performance_rows
from pause_labels import PROFILE, verified_intervals, pause_masks


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--corpus', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    manifest = json.loads(args.corpus.read_text(encoding='utf8'))
    cases = []
    for row in manifest['recordings']:
        wav = args.corpus.parent / row['file']
        samples, rate, cues, fingerprint = read_recording(wav)
        info_path = args.corpus.parent / row['phones_file']
        if fingerprint != row['sha256_pcm'] or read_recording(info_path.parent / f"raw-{row['language']}.wav")[3] != fingerprint:
            raise ValueError('Silence anchors require same-PCM synthesis provenance')
        info = json.loads(info_path.read_text(encoding='utf8'))
        intervals = verified_intervals(samples, rate, performance_rows(wav.read_bytes(), row['duration']), info['phonemes'])
        features, times, _ = audio_features(samples, rate)
        full, safe = pause_masks(intervals, len(features), rate, times)
        labels = labels_at(cues, times, row['duration'])
        cases.append({'id': row['id'], 'language': row['language'], 'split': row['split'],
            'sha256_pcm': fingerprint, 'intervals': intervals, 'all_windows': len(labels),
            'pause_windows': int(full.sum()), 'verified_interior_windows': int(safe.sum()),
            'changed_to_x': int(np.sum(safe & (labels != 'X'))),
            'changes': [{'window_index': int(i), 'time': float(times[i]), 'before': str(labels[i]), 'after': 'X'}
                        for i in np.flatnonzero(safe & (labels != 'X'))],
            'open_labels_inside_verified_silence': int(np.sum(safe & ~np.isin(labels, ['A', 'X'])))})
    args.output.mkdir(parents=True, exist_ok=True)
    report = {'profile': PROFILE, 'originals_preserved': True, 'cases': cases, 'summary': {}}
    for language in ('es', 'en'):
        for split in ('train', 'dev', 'test'):
            subset = [c for c in cases if c['language'] == language and c['split'] == split]
            report['summary'][f'{language}-{split}'] = {key: sum(c[key] for c in subset)
                for key in ('verified_interior_windows', 'changed_to_x', 'open_labels_inside_verified_silence')}
    (args.output / 'pause-label-audit.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps(report['summary']))


if __name__ == '__main__':
    main()
