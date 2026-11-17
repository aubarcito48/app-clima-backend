"""Generate a standalone waveform/cue editor from a local recording."""

import argparse
import base64
import json
from pathlib import Path

import numpy as np

from classifier import labels_at, read_recording


def build(wav, language, output):
    samples, rate, cues, fingerprint = read_recording(wav)
    duration = len(samples) / rate
    if cues:
        labels_at(cues, [], duration)
    else:
        cues = [{'start': 0, 'end': duration, 'value': 'X'}]
    # Seed timelines may have rounding gaps. The editor exposes exact shared
    # boundaries; every interval still starts unreviewed.
    cues = [dict(c) for c in cues]
    previous = 0.
    for index, cue in enumerate(cues):
        cue['start'] = previous
        cue['end'] = duration if index == len(cues) - 1 else min(cue['end'], duration)
        previous = cue['end']
    blocks = np.array_split(samples, min(1500, len(samples)))
    payload = {'version': 1, 'media': 'audio', 'language': language,
               'sha256_pcm': fingerprint, 'duration': duration, 'file': wav.name,
               'peaks': [[round(float(b.min()), 4), round(float(b.max()), 4)] for b in blocks],
               'audio': base64.b64encode(wav.read_bytes()).decode('ascii'),
               'mouthCues': [{**cue, 'reviewed': False} for cue in cues]}
    template = Path(__file__).with_name('audio_editor.html').read_text(encoding='utf8')
    html = template.replace('__ISA_DATA__', json.dumps(payload).replace('<', '\\u003c'))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding='utf8')
    print(json.dumps({'editor': str(output), 'language': language, 'intervals': len(cues)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wav', type=Path, required=True)
    parser.add_argument('--language', choices=('es', 'en'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.wav, args.language, args.output)
