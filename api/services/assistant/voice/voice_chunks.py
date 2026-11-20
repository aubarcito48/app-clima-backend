"""Bound Piper phoneme groups while preserving compound symbols and words."""

import re

MAX_CHUNK_PHONEMES = 64
CELSIUS = re.compile(
    r'(?<![\w.,])([+−-]?\d+(?:[.,]\d+)?)\.?\s*(?:°(?:\s*C(?!\w))?|º\s*C(?!\w))(?!\w)',
    re.IGNORECASE,
)
KILOMETERS_PER_HOUR = re.compile(r'(?<![^\W\d_])km\s*/\s*h(?!\w)', re.IGNORECASE)


def speech_text(text, language='es'):
    def degrees(match):
        number = match.group(1)
        unit = 'grado' if re.fullmatch(r'[+−-]?1(?:[.,]0+)?', number) else 'grados'
        if language == 'en':
            unit = 'degree' if unit == 'grado' else 'degrees'
        return f'{number} {unit}'
    text = CELSIUS.sub(degrees, text)
    def speed_unit(match):
        separator = ' ' if match.start() and text[match.start() - 1].isdigit() else ''
        return separator + ('kilometers per hour' if language == 'en' else 'kilómetros por hora')
    return KILOMETERS_PER_HOUR.sub(speed_unit, text)


def prepare_voice_chunks(voice, text, language='es'):
    return [chunk for sentence in voice.phonemize(speech_text(text, language))
            for chunk in split_voice_phonemes(sentence)]


def split_voice_phonemes(phonemes):
    remaining = list(phonemes)
    while remaining:
        while remaining and remaining[0].isspace():
            remaining.pop(0)
        if not remaining:
            return
        cut = min(len(remaining), MAX_CHUNK_PHONEMES)
        if len(remaining) > cut:
            pauses = [i + 1 for i, value in enumerate(remaining[:cut])
                      if value in '.!?;:,' and i >= cut // 2]
            spaces = [i for i, value in enumerate(remaining[:cut + 1])
                      if i > 0 and value.isspace()]
            cut = pauses[-1] if pauses else spaces[-1] if spaces else cut
        chunk, remaining = remaining[:cut], remaining[cut:]
        while chunk and chunk[-1].isspace():
            chunk.pop()
        if chunk:
            yield chunk


def stream_voice_parts(payload):
    """Group complete phrases without changing text or performance settings."""
    from api.services.assistant.direction.isa_performance import read_segments

    text = payload['texto']
    if payload.get('segmentos'):
        segments = read_segments(payload['segmentos'], text, max_segments=6)
    else:
        segments = [
            {'text': phrase, 'gesture': 'isa-awake', 'speed': 1, 'energy': 1, 'pause_ms': 0}
            for phrase in re.split(r'(?<=[.!?])\s+', ' '.join(text.split())) if phrase
        ]
    groups = []
    for segment in segments:
        limit = 100 if len(groups) <= 1 else 180
        if (groups and len(' '.join(part['text'] for part in groups[-1]))
                + len(segment['text']) + 1 <= limit):
            groups[-1].append(segment)
        else:
            groups.append([segment])
    # At most six frames, even for unusually many short sentences.
    while len(groups) > 6:
        groups[-2].extend(groups.pop())
    result = []
    for group in groups:
        # A neutral undirected text may contain more than six tiny sentences.
        if len(group) > 6:
            group = [{**group[0], 'text': ' '.join(part['text'] for part in group)}]
        result.append({'texto': ' '.join(part['text'] for part in group), 'segmentos': group})
    return result
