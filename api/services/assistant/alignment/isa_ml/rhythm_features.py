"""PCM-only timing channels. No recognizer labels, text or test statistics as input."""
import numpy as np
from api.services.assistant.alignment.isa_ml.classifier import audio_features
PROFILE = 'acoustic-timing-v1'

def _ages(mask, hop, limit):
    output = np.zeros(len(mask))
    age = 0.0
    for i, active in enumerate(mask):
        age = min(limit, age + hop) if active else 0.0
        output[i] = age / limit
    return output

def timing_features(samples, rate):
    base, times, hop = audio_features(samples, rate)
    log_energy = base[:, 24]
    rms = np.exp(log_energy)
    reference = float(np.quantile(rms, 0.9))
    threshold = max(1e-05, min(0.003, reference * 0.025))
    quiet = rms < threshold
    active = ~quiet
    delta = np.zeros(len(base))
    delta[2:] = np.clip((log_energy[2:] - log_energy[:-2]) / 6, -1, 1)
    future = np.zeros(len(base))
    future[:-2] = np.clip((log_energy[2:] - log_energy[:-2]) / 6, -1, 1)
    flux = np.zeros(len(base))
    flux[1:] = np.minimum(1, np.linalg.norm(np.diff(base[:, :24], axis=0), axis=1) / 30)
    onsets = np.r_[False, active[1:] & ~active[:-1]].astype(float)
    radius = max(1, round(0.2 / hop))
    density = np.convolve(np.pad(onsets, (radius, radius)), np.ones(radius * 2 + 1), mode='valid') / 8
    extra = np.column_stack([np.clip((log_energy - np.log(reference + 1e-08)) / 10, -4, 1), quiet.astype(float), _ages(quiet, hop, 0.3), _ages(quiet[::-1], hop, 0.3)[::-1], _ages(active, hop, 0.5), _ages(active[::-1], hop, 0.5)[::-1], delta, future, flux, np.minimum(1, density)])
    return (np.column_stack([base, extra]), times, hop)
