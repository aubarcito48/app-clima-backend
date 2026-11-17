"""Strict binding of manually reviewed cues to a specific PCM recording."""

import json

from classifier import labels_at


def read_annotations(path, fingerprint, language, duration):
    if path.stat().st_size > 262144:
        raise ValueError('Annotation file too large')
    data = json.loads(path.read_text(encoding='utf8'))
    if (not isinstance(data, dict) or data.get('version') != 1
            or data.get('media') != 'audio' or data.get('source') != 'human-reviewed'
            or data.get('language') != language or data.get('sha256_pcm') != fingerprint):
        raise ValueError('Annotation identity, language or provenance mismatch')
    rows = data.get('mouthCues')
    if not isinstance(rows, list) or not rows or any(
            not isinstance(row, dict) or row.get('reviewed') is not True for row in rows):
        raise ValueError('Every audio interval must be explicitly reviewed')
    cues = []
    for row in rows:
        if set(row) != {'start', 'end', 'value', 'reviewed'}:
            raise ValueError('Invalid annotation fields')
        cues.append({k: row[k] for k in ('start', 'end', 'value')})
    labels_at(cues, [], duration)
    previous = 0.
    for cue in cues:
        if abs(cue['start'] - previous) > 1e-6:
            raise ValueError('Reviewed annotations must have no gaps or overlaps')
        previous = cue['end']
    if abs(previous - duration) > 1e-6:
        raise ValueError('Reviewed annotations must cover the exact recording')
    return cues
