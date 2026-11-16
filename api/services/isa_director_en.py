"""English delivery policy, with an opt-in paced profile for isolated Cori trials."""
import re

from .isa_director_shared import split_advice
from .isa_performance import read_segments

_CAUTION = re.compile(r'\b(?:avoid|be careful|take care)\b', re.IGNORECASE)
_LATER = re.compile(r'\b(?:later|tonight|this afternoon|this evening)\b', re.IGNORECASE)
DEFAULT_SPEED = 1.0
DEFAULT_ENERGY = 1.0
DEFAULT_PAUSE_MS = 160


def direct_english(text, *, profile='baseline'):
    if profile not in {'baseline', 'paced-v1'}:
        raise ValueError('Unsupported English delivery profile')
    text, fragments = split_advice(text)
    plan = []
    for index, fragment in enumerate(fragments):
        gesture, speed, energy, pause = 'isa-awake', DEFAULT_SPEED, DEFAULT_ENERGY, DEFAULT_PAUSE_MS
        if _CAUTION.search(fragment):
            gesture, speed, energy, pause = 'isa-down', .96, .96, 220
        elif _LATER.search(fragment):
            gesture, speed, energy, pause = 'isa-right', 1.0, 1.0, 180
        if profile == 'paced-v1':
            words = re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?", fragment)
            speed = .90 if len(words) >= 12 else .92 if len(words) >= 8 else .96
            # Piper already renders punctuation. Avoid stacking a large fixed
            # gap on top of its own sentence ending; never insert word silences.
            pause = 90 if fragment.endswith(';') else 120 if fragment.endswith(('.', '!', '?')) else 60
        plan.append({'text': fragment, 'gesture': gesture, 'speed': speed,
                     'energy': energy, 'pause_ms': pause if index < len(fragments)-1 else 0})
    return read_segments(plan, text)
