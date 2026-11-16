"""English delivery policy; tune independently after reviewing Cori previews.

This initial extraction preserves existing delivery. It does not claim phonetic
alignment or activate the separate experimental frontend pause clock.
"""
import re

from .isa_director_shared import split_advice
from .isa_performance import read_segments

_CAUTION = re.compile(r'\b(?:avoid|be careful|take care)\b', re.IGNORECASE)
_LATER = re.compile(r'\b(?:later|tonight|this afternoon|this evening)\b', re.IGNORECASE)
DEFAULT_SPEED = 1.0
DEFAULT_ENERGY = 1.0
DEFAULT_PAUSE_MS = 160


def direct_english(text):
    text, fragments = split_advice(text)
    plan = []
    for index, fragment in enumerate(fragments):
        gesture, speed, energy, pause = 'isa-awake', DEFAULT_SPEED, DEFAULT_ENERGY, DEFAULT_PAUSE_MS
        if _CAUTION.search(fragment):
            gesture, speed, energy, pause = 'isa-down', .96, .96, 220
        elif _LATER.search(fragment):
            gesture, speed, energy, pause = 'isa-right', 1.0, 1.0, 180
        plan.append({'text': fragment, 'gesture': gesture, 'speed': speed,
                     'energy': energy, 'pause_ms': pause if index < len(fragments)-1 else 0})
    return read_segments(plan, text)
