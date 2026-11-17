"""Quarantine mixed speech/silence boundary windows, never invent phone labels."""
import numpy as np

PROFILE = 'verified-pause-boundary-quarantine-v1'


def boundary_mask(intervals, count, rate):
    window, hop = round(rate*.04), round(rate*.01)
    starts = np.arange(count)*hop-window//2
    ends = starts+window
    overlap, safe = np.zeros(count, bool), np.zeros(count, bool)
    for pause in intervals:
        a, b = pause['start_sample'], pause['end_sample']
        if not 0 <= a < b:
            raise ValueError('Invalid verified interval')
        overlap |= (starts < b) & (ends > a)
        safe |= (starts >= a) & (ends <= b)
    return overlap & ~safe


def apply_quality(row, intervals, rate):
    border = boundary_mask(intervals, len(row['labels']), rate)
    changed = np.flatnonzero(row['labels'] != row['weak_labels'])
    # Only training loss is changed. Evaluation keeps the common repaired target.
    row['boundary_mask'] = border
    return {'id': row['id'], 'language': row['language'], 'split': row['split'],
            'sha256_pcm': row['sha256_pcm'],
            'corrected_windows': [{'index': int(i), 'before': str(row['weak_labels'][i]),
                                   'after': str(row['labels'][i])} for i in changed],
            'quarantined_training_windows': np.flatnonzero(border).tolist() if row['split'] == 'train' else [],
            'ambiguous_boundary_windows': int(border.sum())}
