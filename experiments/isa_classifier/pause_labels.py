"""Authoritative labels only for synthesis-inserted, exactly-zero PCM intervals."""
import math
import numpy as np

PROFILE = 'verified-inserted-pause-interiors-v1'


def sample_index(value, rate):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Invalid synthesis timestamp')
    index = round(value * rate)
    if abs(value * rate - index) > 1e-4:
        raise ValueError('Timestamp is not on the PCM sample grid')
    return index


def verified_intervals(samples, rate, performance, phonemes):
    """Segment metadata plus 20/80 ms gaps in complete same-PCM phone coverage.

    Natural low energy and phoneme punctuation are not evidence of insertion.
    The caller must validate the source PCM hash and the isac performance rows.
    """
    count = len(samples)
    explicit = []
    for row in performance:
        start, end = sample_index(row['speech_end'], rate), sample_index(row['until'], rate)
        if not 0 <= start <= end <= count:
            raise ValueError('Invalid inserted segment pause')
        if end > start:
            explicit.append((start, end))
    covered = []
    for row in phonemes:
        a, b = sample_index(row['start'], rate), sample_index(row['end'], rate)
        if not 0 <= a <= b <= count or covered and a < covered[-1][1]:
            raise ValueError('Invalid phoneme coverage')
        if b > a:
            covered.append((a, b))
    if not covered or covered[0][0] != 0 or covered[-1][1] != count:
        raise ValueError('Incomplete synthesis phone coverage')
    gaps = [(a[1], b[0]) for a, b in zip(covered, covered[1:]) if a[1] < b[0]]
    for a, b in explicit:
        if not any(x <= a and b <= y for x, y in gaps):
            raise ValueError('Pause metadata overlaps synthesized phoneme coverage')
    intervals = []
    for a, b in gaps:
        source = 'inserted_segment_pause' if (a, b) in explicit else 'inserted_chunk_pause'
        if source == 'inserted_chunk_pause' and b - a not in (rate * 20 // 1000, rate * 80 // 1000):
            raise ValueError('Unrecognized synthesis gap; do not relabel it')
        if np.any(samples[a:b] != 0):
            raise ValueError('Claimed inserted pause contains nonzero PCM')
        intervals.append({'start_sample': a, 'end_sample': b, 'start': a / rate, 'end': b / rate,
                          'source': source, 'verified': True})
    return intervals


def pause_masks(intervals, count, rate, times):
    window, hop = round(rate * .04), round(rate * .01)
    if len(times) != count:
        raise ValueError('Feature time grid changed')
    starts = np.arange(count) * hop - window // 2
    ends = starts + window
    # Evaluation on whole pauses is separate from trusted, fully silent windows.
    centers = np.rint(np.asarray(times) * rate).astype(np.int64)
    full, safe = np.zeros(count, dtype=bool), np.zeros(count, dtype=bool)
    for p in intervals:
        a, b = p['start_sample'], p['end_sample']
        full |= (centers >= a) & (centers < b)
        safe |= (starts >= a) & (ends <= b)
    return full, safe


def corrected_labels(labels, safe_mask):
    if len(labels) != len(safe_mask):
        raise ValueError('Label mask does not match recording')
    result = np.array(labels, copy=True)
    result[safe_mask] = 'X'
    return result
