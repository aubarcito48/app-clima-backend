"""Conservative delivery rules; no model, audio analysis or text rewriting."""

import re

from .isa_performance import MAX_SEGMENTS, clean_text, read_segments


_CAUTION = {
    'es': re.compile(r'\b(?:evitá|cuidado|precaución)\b', re.IGNORECASE),
    'en': re.compile(r'\b(?:avoid|be careful|take care)\b', re.IGNORECASE),
}
_LATER = {
    'es': re.compile(r'\b(?:después|más tarde|por la tarde|por la noche|al anochecer)\b', re.IGNORECASE),
    'en': re.compile(r'\b(?:later|tonight|this afternoon|this evening)\b', re.IGNORECASE),
}


def direct_locally(text, *, language='es'):
    """Keep every spoken word, splitting only at sentence/semicolon boundaries.

    These lexical hints are intentionally modest, not a trained classifier or
    an interpretation of the weather. Caution takes precedence over chronology.
    The final segment never adds trailing silence.
    """
    if language not in _CAUTION:
        raise ValueError('Unsupported language')
    text = clean_text(text)
    if not text:
        raise ValueError('Empty advice')
    fragments = re.split(r'(?<=[.!?;])\s+', text)
    if len(fragments) > MAX_SEGMENTS:
        fragments = fragments[:MAX_SEGMENTS - 1] + [' '.join(fragments[MAX_SEGMENTS - 1:])]
    plan = []
    for index, fragment in enumerate(fragments):
        gesture, speed, energy, pause = 'isa-awake', 1.0, 1.0, 160
        if _CAUTION[language].search(fragment):
            gesture, speed, energy, pause = 'isa-down', .96, .96, 220
        elif _LATER[language].search(fragment):
            gesture, speed, energy, pause = 'isa-right', 1.0, 1.0, 180
        plan.append({
            'text': fragment, 'gesture': gesture, 'speed': speed, 'energy': energy,
            'pause_ms': pause if index < len(fragments) - 1 else 0,
        })
    return read_segments(plan, text)
