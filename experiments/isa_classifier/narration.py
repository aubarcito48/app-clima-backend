"""Match the current app's greeting/advice/farewell delivery for local samples."""

import json
import math
import struct

PHRASES = {
    'es': ('¡Buenas, explorador!', '¡Hasta luego, explorador!'),
    'en': ('Hello, explorer!', 'See you later, explorer!'),
}


def app_text(advice, language):
    advice = advice.strip()
    if language not in PHRASES or not advice or len(advice) > 280 or len(advice.split()) > 40:
        raise ValueError('Use a short advice matching the app limits')
    greeting, farewell = PHRASES[language]
    if greeting in advice or farewell in advice:
        raise ValueError('Advice must not already contain the greeting/farewell')
    return f'{greeting}\n{advice}\n{farewell}'


def app_performance(advice, language, director):
    text = app_text(advice, language)
    greeting, farewell = PHRASES[language]
    def neutral(fragment, pause):
        return {'text': fragment, 'gesture': 'isa-awake', 'speed': 1, 'energy': 1, 'pause_ms': pause}
    return text, [neutral(greeting, 160), *director(advice.strip(), language=language), neutral(farewell, 0)]


def performance_rows(audio, duration):
    offset, rows = 12, None
    while offset + 8 <= len(audio):
        size = struct.unpack_from('<I', audio, offset + 4)[0]
        end = offset + 8 + size
        if end > len(audio):
            raise ValueError('Truncated WAV metadata')
        if audio[offset:offset + 4] == b'isac':
            if rows is not None or size > 8192:
                raise ValueError('Invalid performance metadata')
            rows = json.loads(audio[offset + 8:end])
        offset = end + size % 2
    if not isinstance(rows, list) or not 3 <= len(rows) <= 6:
        raise ValueError('Greeting/advice/farewell timings required')
    previous = 0.
    for row in rows:
        values = [row.get(k) for k in ('from', 'speech_end', 'until')]
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
            raise ValueError('Invalid performance time')
        start, end, until = values
        if abs(start - previous) > 1e-6 or not 0 <= start < end <= until <= duration + 1e-6:
            raise ValueError('Invalid performance ordering')
        previous = until
    if abs(previous - duration) > 1e-6:
        raise ValueError('Incomplete performance timings')
    return rows


def advice_spans(audio, duration):
    return [[r['from'], r['speech_end']] for r in performance_rows(audio, duration)[1:-1]]
