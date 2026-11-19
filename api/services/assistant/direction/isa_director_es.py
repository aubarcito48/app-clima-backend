"""Approved Spanish delivery policy, isolated from English tuning."""
import re

from api.services.assistant.direction.isa_director_shared import split_advice
from api.services.assistant.direction.isa_performance import read_segments

_CAUTION = re.compile(r'\b(?:evitá|cuidado|precaución)\b', re.IGNORECASE)
_LATER = re.compile(r'\b(?:después|más tarde|por la tarde|por la noche|al anochecer)\b', re.IGNORECASE)


def direct_spanish(text):
    text, fragments = split_advice(text)
    plan = []
    for index, fragment in enumerate(fragments):
        gesture, speed, energy, pause = 'isa-awake', 1.0, 1.0, 160
        if _CAUTION.search(fragment):
            gesture, speed, energy, pause = 'isa-down', .96, .96, 220
        elif _LATER.search(fragment):
            gesture, speed, energy, pause = 'isa-right', 1.0, 1.0, 180
        plan.append({'text': fragment, 'gesture': gesture, 'speed': speed,
                     'energy': energy, 'pause_ms': pause if index < len(fragments)-1 else 0})
    return read_segments(plan, text)
