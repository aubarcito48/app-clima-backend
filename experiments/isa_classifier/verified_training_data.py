"""Shared, model-independent preparation for comparisons with repaired pauses."""
import json
import numpy as np
from classifier import read_recording
from narration import advice_spans, performance_rows
from phoneme_identity import identity_features, vocabulary_from_training
from phonetic_features import hybrid_features
from rhythm_features import timing_features
from train_short import core_mask
from pause_labels import verified_intervals, pause_masks, corrected_labels


def prepare_language(rows, language, corpus):
    subset = [r for r in rows if r['language'] == language and (r['split'] != 'test' or r.get('evaluation') == 'fresh')]
    groups = {}
    for row in subset:
        key = row.get('group_id', row['id'])
        identity = (row['split'], row['text'])
        if key in groups and groups[key] != identity:
            raise ValueError('Rate variants crossed text or split')
        groups[key] = identity
    infos = {r['id']: json.loads((corpus.parent/r['phones_file']).read_text(encoding='utf8')) for r in subset}
    vocabulary = vocabulary_from_training([infos[r['id']] for r in subset if r['split'] == 'train'])
    train_groups = {}
    for row in subset:
        if row['split'] == 'train':
            key = row.get('group_id', row['id']); train_groups[key] = train_groups.get(key, 0)+1
    for row in subset:
        wav = corpus.parent/row['file']
        samples, rate, _, fingerprint = read_recording(wav)
        if fingerprint != row['sha256_pcm'] or advice_spans(wav.read_bytes(), row['duration']) != row['advice_spans']:
            raise ValueError('PCM or advice spans changed')
        info = infos[row['id']]
        if info['text'] != row['text'] or read_recording((corpus.parent/row['phones_file']).parent/f'raw-{language}.wav')[3] != fingerprint:
            raise ValueError('Phonetic provenance changed')
        info['sha256_pcm'] = fingerprint
        row['identity_features'], times, _ = identity_features(samples, rate, info, vocabulary)
        row['identity_vocabulary'] = vocabulary
        row['phonetic_features'], _, _ = hybrid_features(samples, rate, info)
        row['timing_features'], _, _ = timing_features(samples, rate)
        original_advice_mask = core_mask(row)
        performance = performance_rows(wav.read_bytes(), row['duration'])
        segment = np.zeros(len(times), dtype=bool)
        for p in performance:
            segment |= (times >= p['speech_end']) & (times < p['until'])
        row['segment_pause_mask'] = segment
        intervals = verified_intervals(samples, rate, performance, info['phonemes'])
        full, safe = pause_masks(intervals, len(times), rate, times)
        row['weak_labels'] = row['labels'].copy()
        row['labels'] = corrected_labels(row['labels'], safe)
        row['safe_pause_mask'], row['known_pause_mask'] = safe, full
        row['advice_mask'] = original_advice_mask & ~full
        row['focus'] = np.where(original_advice_mask, 1., .25)/train_groups.get(row.get('group_id', row['id']), 1)
    return subset, vocabulary
