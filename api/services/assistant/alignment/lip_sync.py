"""Bounded mouth cues and WAV metadata for Isa synchronization."""

import json
import math

MAX_CUE_BYTES = 65536
MAX_CUES = 1500
SHAPES = frozenset('ABCDEFGHX')


def read_mouth_cues(data, duration):
    """Only bounded, contiguous audio-relative times and real Rhubarb shapes."""
    rows = data.get('mouthCues') if isinstance(data, dict) else None
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_CUES:
        raise ValueError('Invalid mouth cues')
    result, previous = [], 0.0
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'start', 'end', 'value'}:
            raise ValueError('Invalid mouth cue')
        start, end, shape = row['start'], row['end'], row['value']
        if (any(isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) for value in (start, end))
                or not isinstance(shape, str) or shape not in SHAPES
                or not 0 <= start < end <= duration + .011
                or abs(start - previous) > .011):
            raise ValueError('Invalid mouth cue timing')
        result.append({'start': start, 'end': end, 'value': shape})
        previous = end
    if abs(previous - duration) > .021:
        raise ValueError('Incomplete mouth timeline')
    payload = json.dumps(result, separators=(',', ':'), allow_nan=False).encode('ascii')
    if len(payload) > MAX_CUE_BYTES:
        raise ValueError('Mouth timeline too large')
    return result


def append_mouth_cues(audio, cues):
    # Separate from isac: existing consumers continue reading segment timings.
    payload = json.dumps(cues, separators=(',', ':'), allow_nan=False).encode('ascii')
    chunk = b'isav' + len(payload).to_bytes(4, 'little') + payload
    chunk += b'\x00' * (len(payload) % 2)
    result = audio + chunk
    return result[:4] + (len(result) - 8).to_bytes(4, 'little') + result[8:]
