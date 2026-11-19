"""Audio features and timelines used by Isa inference."""
import hashlib
import io
import json
from pathlib import Path
import struct
import wave
import numpy as np
SHAPES = tuple('ABCDEFGHX')
VERSION = 'isa-centroid-v1'

def audio_features(samples, rate):
    """40 ms spectral windows every 10 ms, including the final partial hop."""
    window, hop = (round(rate * 0.04), round(rate * 0.01))
    count = (len(samples) + hop - 1) // hop
    padded = np.pad(samples, (window // 2, window))
    frames = np.stack([padded[i * hop:i * hop + window] for i in range(count)])
    rms = np.sqrt(np.mean(frames * frames, axis=1))
    power = np.abs(np.fft.rfft(frames * np.hanning(window), axis=1)) ** 2
    frequencies = np.fft.rfftfreq(window, 1 / rate)
    edges = np.geomspace(60, min(7600, rate / 2), 25)
    bands = np.stack([np.log(np.mean(power[:, (frequencies >= low) & (frequencies < high)], axis=1) + 1e-10) if np.any((frequencies >= low) & (frequencies < high)) else np.full(count, -23.0) for low, high in zip(edges[:-1], edges[1:])], axis=1)
    bands -= bands.mean(axis=1, keepdims=True)
    zcr = np.mean(np.diff(np.signbit(frames), axis=1), axis=1)
    features = np.column_stack([bands, np.log(rms + 1e-08), zcr])
    times = np.minimum((np.arange(count) + 0.5) * hop / rate, len(samples) / rate - 1e-09)
    return (features, times, hop / rate)

def labels_at(cues, times, duration):
    if not isinstance(cues, list) or not 1 <= len(cues) <= 1500:
        raise ValueError('A labelled reference is required')
    previous = 0.0
    for cue in cues:
        if not isinstance(cue, dict) or set(cue) != {'start', 'end', 'value'}:
            raise ValueError('Invalid label')
        start, end, shape = (cue['start'], cue['end'], cue['value'])
        if any((isinstance(v, bool) or not isinstance(v, (int, float)) or (not np.isfinite(v)) for v in (start, end))) or not isinstance(shape, str) or shape not in SHAPES or (abs(start - previous) > 0.011) or (not 0 <= start < end <= duration + 0.011):
            raise ValueError('Invalid label timeline')
        previous = end
    if abs(previous - duration) > 0.021:
        raise ValueError('Incomplete labels')
    indices = np.searchsorted([c['end'] for c in cues], times, side='right')
    return np.array([cues[min(int(i), len(cues) - 1)]['value'] for i in indices])

def timeline(labels, hop, duration):
    if not len(labels) or hop <= 0 or duration <= 0 or ((len(labels) - 1) * hop >= duration):
        raise ValueError('Invalid timeline length')
    cues, first = ([], 0)
    for i in range(1, len(labels) + 1):
        if i == len(labels) or labels[i] != labels[first]:
            cues.append({'start': round(first * hop, 6), 'end': round(min(i * hop, duration), 6), 'value': str(labels[first])})
            first = i
    return cues
