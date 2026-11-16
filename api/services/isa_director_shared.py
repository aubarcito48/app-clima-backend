"""Shared text bounds only; language delivery choices live in separate modules."""
import re

from .isa_performance import MAX_SEGMENTS, clean_text


def split_advice(text):
    text = clean_text(text)
    if not text:
        raise ValueError('Empty advice')
    fragments = re.split(r'(?<=[.!?;])\s+', text)
    if len(fragments) > MAX_SEGMENTS:
        fragments = fragments[:MAX_SEGMENTS - 1] + [' '.join(fragments[MAX_SEGMENTS - 1:])]
    return text, fragments
