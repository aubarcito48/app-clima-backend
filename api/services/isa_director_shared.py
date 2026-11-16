"""Shared text bounds only; language delivery choices live in separate modules."""
import re

from .isa_performance import MAX_SEGMENTS, clean_text


def split_advice(text):
    text = clean_text(text)
    if not text:
        raise ValueError('Empty advice')
    # A stray period before a degree sign is a unit-formatting error, not the
    # end of an utterance. Keep the value/unit together for speech normalization.
    fragments = re.split(r'(?<=[.!?;])\s+(?!\s*[°º])', text)
    if len(fragments) > MAX_SEGMENTS:
        fragments = fragments[:MAX_SEGMENTS - 1] + [' '.join(fragments[MAX_SEGMENTS - 1:])]
    return text, fragments
