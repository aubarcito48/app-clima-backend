"""Bounded experimental two-pass rate controller; no human sliders required."""
import math

PROFILES = {'en': {'target_words_per_second': 2.65, 'minimum_factor': .90},
            'es': {'target_words_per_second': 2.85, 'minimum_factor': .94}}


def rate_plan(timing):
    profile = PROFILES[timing['language']]
    factors, decisions = [], []
    for segment in timing['segments']:
        wps = segment['words_per_second']
        if not isinstance(wps, (int, float)) or not math.isfinite(wps) or wps <= 0:
            raise ValueError('Invalid measured speaking rate')
        factor = 1.
        if segment['role'] == 'advice':
            factor = max(profile['minimum_factor'], min(1., profile['target_words_per_second'] / wps))
            if factor > .99:
                factor = 1.  # Do not resynthesize for tiny fluctuations.
        factors.append(round(factor, 4))
        decisions.append({'text': segment['text'], 'role': segment['role'], 'measured_wps': wps,
                          'factor': factors[-1], 'reason': 'fast_advice' if factor < 1 else 'keep_current'})
    return factors, decisions
