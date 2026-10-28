"""Límite de pronunciación después de expandir números, unidades y abreviaturas."""

import re

MAX_CHUNK_PHONEMES = 32


def prepare_voice_chunks(tokenizer, text):
    return list(split_voice_phonemes(tokenizer.phonemize(text, lang='es')))


def split_voice_phonemes(phonemes):
    remaining = phonemes.strip()
    while len(remaining) > MAX_CHUNK_PHONEMES:
        prefix = remaining[:MAX_CHUNK_PHONEMES + 1]
        pauses = [match.end() for match in re.finditer(r'[.!?;:,](?=\s)', prefix)
                  if match.end() >= MAX_CHUNK_PHONEMES // 2]
        spaces = [match.start() for match in re.finditer(r'\s+', prefix)
                  if 0 < match.start() <= MAX_CHUNK_PHONEMES]
        cut = pauses[-1] if pauses else spaces[-1] if spaces else MAX_CHUNK_PHONEMES
        yield remaining[:cut].strip()
        remaining = remaining[cut:].strip()
    if remaining:
        yield remaining
