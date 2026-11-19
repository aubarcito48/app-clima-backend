"""Isa's actual portrait catalogue and bounded, text-preserving performance plans."""

import json
import math
import unicodedata

GESTURES = ('isa-awake', 'isa-right', 'isa-down')
MAX_SEGMENTS = 4


def clean_text(text):
    if not isinstance(text, str) or any(
        unicodedata.category(char) in {'Cc', 'Cf', 'Cs'} and char not in '\n\r\t'
        for char in text
    ):
        raise ValueError('Invalid text')
    return unicodedata.normalize('NFC', ' '.join(text.split()))


def read_segments(items, text, *, max_segments=MAX_SEGMENTS):
    if not isinstance(items, list) or not 1 <= len(items) <= max_segments:
        raise ValueError('Invalid segments')
    result = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {'text', 'gesture', 'speed', 'energy', 'pause_ms'}:
            raise ValueError('Invalid segment')
        fragment = clean_text(item['text'])
        if not fragment or len(fragment) > 600 or item['gesture'] not in GESTURES:
            raise ValueError('Invalid gesture or text')
        for name, low, high in (('speed', .8, 1.2), ('energy', .65, 1.2), ('pause_ms', 0, 600)):
            value = item[name]
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or not low <= value <= high):
                raise ValueError('Invalid delivery')
        if not isinstance(item['pause_ms'], int):
            raise ValueError('Invalid pause')
        result.append({**item, 'text': fragment})
    if ' '.join(item['text'] for item in result) != clean_text(text):
        raise ValueError('Performance changed the spoken text')
    return result


def append_timeline(audio, timeline):
    """A standard optional RIFF chunk: the WAV remains playable on its own."""
    payload = json.dumps(timeline, separators=(',', ':'), allow_nan=False).encode('utf-8')
    chunk = b'isac' + len(payload).to_bytes(4, 'little') + payload
    chunk += b'\x00' * (len(payload) % 2)
    result = audio + chunk
    return result[:4] + (len(result) - 8).to_bytes(4, 'little') + result[8:]
