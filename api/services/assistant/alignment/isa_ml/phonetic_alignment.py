"""Experimental IPA -> existing visemes. No production integration or training.

Durations come from Piper's synthesis graph, including padding after each phone.
Word separators and stress/length marks are not silent phonemes. Their duration
is attached to neighbouring articulations; only explicit pauses use X.
"""
import math
COMMON = {**dict.fromkeys('pbm', 'A'), **dict.fromkeys('fv', 'G'), **dict.fromkeys('lɫ', 'H'), **dict.fromkeys('iuɪɨy', 'B'), **dict.fromkeys('eɛæɜəɐ', 'C'), **dict.fromkeys('aɑɒ', 'D'), **dict.fromkeys('oɔœø', 'E'), **dict.fromkeys('uʊwʉ', 'F'), **dict.fromkeys('tdkszʃʒʧʤθðnŋɲrɾɹɻhjɟɡgxcçʎβɣɸʔ', 'B')}
PROFILES = {'es': {**COMMON, 'a': 'D', 'e': 'C', 'o': 'E', 'ʝ': 'B'}, 'en': {**COMMON, 'ɚ': 'E', 'ɝ': 'E', 'ʌ': 'D'}}
MARKS = set('ˈˌːˑ̩̯̃ʲʰ')
REST = set('^$.,!?;:')
DIPHTHONGS = {'eɪ', 'aɪ', 'aʊ', 'oʊ', 'əʊ', 'ɔɪ', 'ɪə', 'eə', 'ʊə'}

def expand_diphthongs(rows):
    """Piper gives total duration, not the internal boundary: split is heuristic."""
    result = []
    for row in rows:
        if row['phoneme'] in DIPHTHONGS:
            first = row['samples'] // 2
            result.extend(({'phoneme': phone, 'samples': size, 'source_phoneme': row['phoneme'], 'internal_boundary': 'estimated_equal_split'} for phone, size in zip(row['phoneme'], (first, row['samples'] - first))))
        else:
            result.append(row)
    return result

def grouped_durations(phonemes, id_map, ids, counts, audio_frames):
    """Mirror Piper BOS/PAD/phone/PAD/EOS encoding; fail on dropped symbols."""
    if len(ids) != len(counts) or any((not math.isfinite(float(n)) or n < 0 or int(n) != n for n in counts)):
        raise ValueError('Invalid per-ID duration output')
    if sum((int(n) for n in counts)) != audio_frames:
        raise ValueError('Alignment does not cover the synthesized PCM')
    offset, result = (0, [])
    for phone in ['^', *phonemes, '$']:
        if phone not in id_map:
            raise ValueError(f'Unencoded phoneme: {phone!r}')
        expected = list(id_map[phone]) + (list(id_map['_']) if phone != '$' else [])
        if ids[offset:offset + len(expected)] != expected:
            raise ValueError('Phoneme ID alignment mismatch')
        size = sum((int(n) for n in counts[offset:offset + len(expected)]))
        result.append({'phoneme': phone, 'samples': size})
        offset += len(expected)
    if offset != len(ids):
        raise ValueError('Unconsumed phoneme IDs')
    return result

def phone_shapes(rows, language):
    profile = PROFILES[language]
    unknown = sorted({r['phoneme'] for r in rows if r['phoneme'] not in profile and r['phoneme'] not in MARKS | REST | {' '}})
    if unknown:
        raise ValueError(f'Unmapped {language} IPA symbols: {unknown!r}')
    shapes = [profile.get(r['phoneme'], 'X' if r['phoneme'] in REST else None) for r in rows]
    for i, row in enumerate(rows):
        if shapes[i] is not None:
            continue
        order = list(range(i + 1, len(rows))) + list(range(i - 1, -1, -1)) if row['phoneme'] in 'ˈˌ' else list(range(i - 1, -1, -1)) + list(range(i + 1, len(rows)))
        shapes[i] = next((profile[rows[j]['phoneme']] for j in order if rows[j]['phoneme'] in profile), 'X')
    return shapes

def append_cue(cues, start, end, shape):
    if end <= start:
        return
    if cues and cues[-1]['value'] == shape and (abs(cues[-1]['end'] - start) < 1e-08):
        cues[-1]['end'] = end
    else:
        cues.append({'start': start, 'end': end, 'value': shape})
