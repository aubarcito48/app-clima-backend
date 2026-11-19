"""Offline timing diagnostics, not word alignment or automatic ground truth."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from api.services.assistant.direction.isa_local_director import direct_locally
from classifier import read_recording
from narration import app_performance, performance_rows


def quiet_candidates(samples, rate, *, minimum_ms=25):
    hop = max(1, round(rate * .005))
    count = (len(samples) + hop - 1) // hop
    padded = np.pad(samples, (0, count * hop - len(samples))).reshape(count, hop)
    rms = np.sqrt(np.mean(padded ** 2, axis=1))
    threshold = max(1e-5, min(.003, float(np.quantile(rms, .9)) * .025))
    quiet = rms < threshold
    edges = np.flatnonzero(np.diff(np.r_[False, quiet, False]))
    result = []
    for first, end in zip(edges[::2], edges[1::2]):
        start, until = first * hop / rate, min(len(samples), end * hop) / rate
        if (until - start) * 1000 >= minimum_ms:
            result.append({'start': start, 'end': until, 'duration_ms': (until - start) * 1000,
                           'kind': 'quiet_long_candidate' if until - start >= .15 else 'quiet_short_candidate',
                           'verified': False, 'word_boundary': False})
    return result, threshold, rms, hop


def analyze(wav, sample):
    values, rate, _, fingerprint = read_recording(wav)
    if fingerprint != sample['sha256_pcm']:
        raise ValueError('Demo audio changed')
    spoken, segments = app_performance(sample['advice'], sample['language'], direct_locally)
    if sample['text'] != spoken:
        raise ValueError('The timing test requires the exact app narration')
    rows = performance_rows(wav.read_bytes(), sample['duration'])
    if len(rows) != len(segments):
        raise ValueError('Performance segment count changed')
    candidates, threshold, rms, hop = quiet_candidates(values, rate)
    pauses, fragments = [], []
    for index, (row, segment) in enumerate(zip(rows, segments)):
        word_count = len(segment['text'].split())
        fragments.append({**row, 'text': segment['text'], 'words': word_count,
                          'role': 'greeting' if index == 0 else 'farewell' if index == len(rows) - 1 else 'advice',
                          'words_per_second': word_count / (row['speech_end'] - row['from'])})
        if row['until'] > row['speech_end']:
            pauses.append({'start': row['speech_end'], 'end': row['until'],
                           'duration_ms': (row['until'] - row['speech_end']) * 1000,
                           'kind': 'inserted_segment_pause', 'verified': True,
                           'sentence_end': segment['text'].rstrip().endswith(('.', '!', '?'))})
    # Keep the overview bounded; original 5 ms analysis remains in candidate times.
    display = np.array_split(rms, min(1200, len(rms)))
    body = fragments[1:-1]
    return {'language': sample['language'], 'sha256_pcm': fingerprint, 'duration': sample['duration'],
            'quiet_threshold': threshold, 'analysis_hop_ms': hop / rate * 1000,
            'quiet_candidates': candidates, 'inserted_pauses': pauses, 'segments': fragments,
            'advice_words_per_second': sum(r['words'] for r in body) / sum(r['speech_end'] - r['from'] for r in body),
            'envelope': [float(np.max(block)) for block in display],
            'warning': 'quiet energy is not a verified silence or word boundary; words have no forced alignment'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--integrated', action='store_true', help='Compare V7 and phonetic cues with the same timing planner')
    args = parser.parse_args()
    original = json.loads((args.demo / 'demo.json').read_text(encoding='utf8'))
    if args.integrated and any(not {'v7', 'v8'} <= set(case['versions']) or not case.get('phonemes')
                               for case in original['cases']):
        parser.error('Integrated comparison requires V7, phonetic cues and phoneme timings')
    analyses = [analyze(args.demo / f"demo-{s['language']}.wav", s) for s in original['cases']]
    args.output.mkdir(parents=True, exist_ok=True)
    result = {'cases': original['cases'], 'timing': analyses}
    if args.integrated:
        result['integrated'] = True
    (args.output / 'timing.json').write_text(json.dumps(result), encoding='utf8')
    print(json.dumps({r['language']: {'candidate_gaps': len(r['quiet_candidates']),
        'known_pauses': len(r['inserted_pauses']), 'advice_words_per_second': round(r['advice_words_per_second'], 2)}
        for r in analyses}))


if __name__ == '__main__':
    main()
