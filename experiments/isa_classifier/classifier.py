"""Offline baseline; never imported by Django or the production voice worker."""

import hashlib
import io
import json
from pathlib import Path
import struct
import wave

import numpy as np

SHAPES = tuple('ABCDEFGHX')
VERSION = 'isa-centroid-v1'


def read_recording(path):
    data = Path(path).read_bytes()
    if len(data) > 8_000_000 or data[:4] != b'RIFF' or data[8:12] != b'WAVE':
        raise ValueError('Expected a bounded RIFF WAV')
    if int.from_bytes(data[4:8], 'little') + 8 != len(data):
        raise ValueError('Invalid RIFF length')
    with wave.open(io.BytesIO(data)) as source:
        rate = source.getframerate()
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise ValueError('Expected mono PCM16')
        if not 8000 <= rate <= 48000 or not 0 < source.getnframes() <= rate * 90:
            raise ValueError('Unsupported sample rate or duration')
        pcm = source.readframes(source.getnframes())
    samples = np.frombuffer(pcm, dtype='<i2').astype(np.float64) / 32768
    if not len(samples):
        raise ValueError('Empty audio')
    cues, offset = None, 12
    while offset + 8 <= len(data):
        size = struct.unpack_from('<I', data, offset + 4)[0]
        end = offset + 8 + size
        if end > len(data):
            raise ValueError('Truncated WAV chunk')
        if data[offset:offset + 4] == b'isav':
            if cues is not None or size > 65536:
                raise ValueError('Duplicate or oversized labels')
            cues = json.loads(data[offset + 8:end])
        offset = end + size % 2
    if offset != len(data):
        raise ValueError('Invalid chunk padding')
    # Hash PCM, not the container: copies with different metadata cannot leak
    # across train/test. This does not detect alternate takes of the same text.
    fingerprint = hashlib.sha256(struct.pack('<I', rate) + pcm).hexdigest()
    return samples, rate, cues, fingerprint


def audio_features(samples, rate):
    """40 ms spectral windows every 10 ms, including the final partial hop."""
    window, hop = round(rate * .04), round(rate * .01)
    count = (len(samples) + hop - 1) // hop
    padded = np.pad(samples, (window // 2, window))
    frames = np.stack([padded[i * hop:i * hop + window] for i in range(count)])
    rms = np.sqrt(np.mean(frames * frames, axis=1))
    power = np.abs(np.fft.rfft(frames * np.hanning(window), axis=1)) ** 2
    frequencies = np.fft.rfftfreq(window, 1 / rate)
    edges = np.geomspace(60, min(7600, rate / 2), 25)
    bands = np.stack([
        np.log(np.mean(power[:, (frequencies >= low) & (frequencies < high)], axis=1) + 1e-10)
        if np.any((frequencies >= low) & (frequencies < high)) else np.full(count, -23.)
        for low, high in zip(edges[:-1], edges[1:])
    ], axis=1)
    bands -= bands.mean(axis=1, keepdims=True)
    zcr = np.mean(np.diff(np.signbit(frames), axis=1), axis=1)
    features = np.column_stack([bands, np.log(rms + 1e-8), zcr])
    times = np.minimum((np.arange(count) + .5) * hop / rate, len(samples) / rate - 1e-9)
    return features, times, hop / rate


def labels_at(cues, times, duration):
    if not isinstance(cues, list) or not 1 <= len(cues) <= 1500:
        raise ValueError('A labelled reference is required')
    previous = 0.
    for cue in cues:
        if not isinstance(cue, dict) or set(cue) != {'start', 'end', 'value'}:
            raise ValueError('Invalid label')
        start, end, shape = cue['start'], cue['end'], cue['value']
        if (any(isinstance(v, bool) or not isinstance(v, (int, float)) or not np.isfinite(v)
                for v in (start, end)) or not isinstance(shape, str) or shape not in SHAPES
                or abs(start - previous) > .011 or not 0 <= start < end <= duration + .011):
            raise ValueError('Invalid label timeline')
        previous = end
    if abs(previous - duration) > .021:
        raise ValueError('Incomplete labels')
    indices = np.searchsorted([c['end'] for c in cues], times, side='right')
    return np.array([cues[min(int(i), len(cues) - 1)]['value'] for i in indices])


def fit(features, labels):
    features = np.asarray(features, dtype=float)
    labels = np.asarray(labels)
    if features.ndim != 2 or len(features) != len(labels) or not len(features):
        raise ValueError('Invalid training rows')
    if not np.isfinite(features).all() or any(label not in SHAPES for label in labels):
        raise ValueError('Invalid training values')
    mean = features.mean(axis=0)
    scale = np.maximum(features.std(axis=0), .05)
    normalized = (features - mean) / scale
    classes = sorted(set(labels.tolist()))
    return {'version': VERSION, 'classes': classes, 'mean': mean.tolist(),
            'scale': scale.tolist(), 'centroids': [normalized[labels == c].mean(axis=0).tolist()
                                                 for c in classes],
            'counts': {c: int(np.sum(labels == c)) for c in classes}}


def classify(model, features):
    if model['version'] != VERSION:
        raise ValueError('Unknown classifier version')
    values = (np.asarray(features) - np.array(model['mean'])) / np.array(model['scale'])
    distances = np.mean((values[:, None, :] - np.array(model['centroids'])[None, :, :]) ** 2, axis=2)
    ranking = np.argsort(distances, axis=1)
    labels = np.array(model['classes'])[ranking[:, 0]]
    # Distance margin is a ranking diagnostic, not a calibrated probability.
    margin = (distances[np.arange(len(values)), ranking[:, 1]] - distances.min(axis=1)
              if len(model['classes']) > 1 else np.zeros(len(values)))
    return labels, margin


def smooth(labels):
    result = labels.copy()
    for i in range(1, len(labels) - 1):
        if labels[i - 1] == labels[i + 1]:
            result[i] = labels[i - 1]
    return result


def timeline(labels, hop, duration):
    if not len(labels) or hop <= 0 or duration <= 0 or (len(labels) - 1) * hop >= duration:
        raise ValueError('Invalid timeline length')
    cues, first = [], 0
    for i in range(1, len(labels) + 1):
        if i == len(labels) or labels[i] != labels[first]:
            cues.append({'start': round(first * hop, 6),
                         'end': round(min(i * hop, duration), 6), 'value': str(labels[first])})
            first = i
    return cues


def metrics(expected, predicted):
    classes = sorted(set(expected.tolist()) | set(predicted.tolist()))
    recalls, precision, f1 = {}, {}, {}
    for label in classes:
        mask = expected == label
        recalls[label] = float(np.mean(predicted[mask] == label)) if mask.any() else None
        positive = predicted == label
        correct = int(np.sum(mask & positive))
        precision[label] = correct / int(positive.sum()) if positive.any() else 0.
        f1[label] = 2 * correct / int(mask.sum() + positive.sum())
    return {'frame_agreement': float(np.mean(expected == predicted)),
            'balanced_recall': float(np.mean([v for v in recalls.values() if v is not None])),
            'macro_f1': float(np.mean(list(f1.values()))),
            'precision_by_shape': precision, 'f1_by_shape': f1,
            'recall_by_shape': recalls, 'confusion': {
                a: {b: int(np.sum((expected == a) & (predicted == b))) for b in classes}
                for a in classes}}
