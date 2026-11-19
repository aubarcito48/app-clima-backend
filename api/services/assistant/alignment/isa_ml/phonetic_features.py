"""Hybrid inference requires matching synthesis phones as well as PCM."""
import numpy as np
import hashlib
import struct
from api.services.assistant.alignment.isa_ml.classifier import SHAPES
from api.services.assistant.alignment.isa_ml.classifier import labels_at
PROFILE = 'acoustic-timing-phonetic-v1'

def hybrid_features(samples, rate, alignment):
    from api.services.assistant.alignment.isa_ml.rhythm_features import timing_features
    base, times, hop = timing_features(samples, rate)
    duration = len(samples) / rate
    if alignment is None:
        raise ValueError('Hybrid inference requires same-PCM Piper alignments')
    pcm = np.rint(samples * 32768).astype('<i2').tobytes()
    fingerprint = hashlib.sha256(struct.pack('<I', rate) + pcm).hexdigest()
    if alignment.get('sha256_pcm') != fingerprint:
        raise ValueError('Phonetic alignment belongs to different PCM')
    labels = labels_at(alignment['cues'], times, duration)
    phones = [r for r in alignment['phonemes'] if r['end'] > r['start']]
    if not phones or abs(phones[-1]['end'] - duration) > 1e-08:
        raise ValueError('Phonemes do not cover audio duration')
    starts = np.array([r['start'] for r in phones])
    ends = np.array([r['end'] for r in phones])
    if not np.isfinite(starts).all() or not np.isfinite(ends).all() or starts[0] < 0 or np.any(starts[1:] < ends[:-1] - 1e-08):
        raise ValueError('Invalid phoneme intervals')
    indices = np.clip(np.searchsorted(starts, times, side='right') - 1, 0, len(starts) - 1)
    active = (times >= starts[indices]) & (times < ends[indices])
    elapsed = np.where(active, np.minimum(1, (times - starts[indices]) / 0.3), 0)
    remaining = np.where(active, np.minimum(1, (ends[indices] - times) / 0.3), 0)
    length = np.where(active, np.minimum(4, (ends[indices] - starts[indices]) / 0.5), 0)
    onehot = np.column_stack([labels == shape for shape in SHAPES]).astype(float)
    features = np.column_stack([base, onehot, elapsed, remaining, length])
    if not np.isfinite(features).all():
        raise ValueError('Invalid hybrid features')
    return (features, times, hop)
