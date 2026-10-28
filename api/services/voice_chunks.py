"""Bound Piper phoneme groups while preserving compound symbols and words."""

import re

MAX_CHUNK_PHONEMES = 64
CELSIUS = re.compile(r'(?<![\w.,])([+−-]?\d+(?:[.,]\d+)?)\s*[°º]\s*C(?!\w)', re.IGNORECASE)


def speech_text(text):
    def degrees(match):
        number = match.group(1)
        unit = 'grado' if re.fullmatch(r'[+−-]?1(?:[.,]0+)?', number) else 'grados'
        return f'{number} {unit}'
    return CELSIUS.sub(degrees, text)


def prepare_voice_chunks(voice, text):
    return [chunk for sentence in voice.phonemize(speech_text(text))
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
