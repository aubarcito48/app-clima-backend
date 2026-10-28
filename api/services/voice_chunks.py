"""Fragmentos pequeños sin omitir palabras ni confundir decimales con pausas."""

import re

MAX_CHUNK_CHARACTERS = 80


def split_voice_text(text):
    remaining = text.strip()
    while len(remaining) > MAX_CHUNK_CHARACTERS:
        prefix = remaining[:MAX_CHUNK_CHARACTERS + 1]
        pauses = [match.end() for match in re.finditer(r'[.!?;:,](?=\s)', prefix)
                  if match.end() >= MAX_CHUNK_CHARACTERS // 2]
        spaces = [match.start() for match in re.finditer(r'\s+', prefix)
                  if 0 < match.start() <= MAX_CHUNK_CHARACTERS]
        cut = pauses[-1] if pauses else spaces[-1] if spaces else MAX_CHUNK_CHARACTERS
        yield remaining[:cut].strip()
        remaining = remaining[cut:].strip()
    if remaining:
        yield remaining
