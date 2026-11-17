"""Isolated experimental boosted-tree probabilities plus temporal decoding."""
import base64
from functools import lru_cache
import numpy as np
from temporal import OFFSETS

VERSION = 'isa-boosted-phonemes-v1'


def tree_context(features):
    values = np.asarray(features, dtype=np.float32)
    if values.ndim != 2 or not len(values) or not np.isfinite(values).all():
        raise ValueError('Invalid boosted input')
    indices = np.arange(len(values))
    return np.concatenate([values[np.clip(indices + offset, 0, len(values) - 1)] for offset in OFFSETS], axis=1)


@lru_cache(maxsize=2)
def load_booster(encoded):
    import xgboost as xgb
    model = xgb.Booster(params={'nthread': 2})
    model.load_model(bytearray(base64.b64decode(encoded, validate=True)))
    model.set_param({'nthread': 2})
    return model


def probabilities(booster, features):
    return booster.inplace_predict(tree_context(features))


def decode(model, probabilities):
    p = np.asarray(probabilities, dtype=float)
    if (p.ndim != 2 or not len(p) or p.shape[1] != len(model['classes'])
            or not np.isfinite(p).all() or np.any(p < 0) or np.any(p > 1)
            or not np.allclose(p.sum(axis=1), 1, atol=1e-5)):
        raise ValueError('Invalid class probabilities')
    scores = np.log(np.maximum(p, 1e-9))
    penalty, strength = model['closure_penalty'], model['transition_strength']
    if penalty not in (0., .25) or strength not in (0., .05):
        raise ValueError('Unsupported frozen decoder calibration')
    scores[:, [i for i, c in enumerate(model['classes']) if c in 'AX']] -= penalty
    if not strength:
        return np.array(model['classes'])[scores.argmax(axis=1)]
    transition = np.array(model['log_transitions']) * strength
    if transition.shape != (p.shape[1], p.shape[1]) or not np.isfinite(transition).all():
        raise ValueError('Invalid learned transitions')
    back = np.zeros(p.shape, dtype=np.int32)
    previous = scores[0]
    for i in range(1, len(p)):
        paths = previous[:, None] + transition
        back[i] = paths.argmax(axis=0)
        previous = scores[i] + paths.max(axis=0)
    path = np.empty(len(p), dtype=int); path[-1] = previous.argmax()
    for i in range(len(p) - 1, 0, -1):
        path[i - 1] = back[i, path[i]]
    return np.array(model['classes'])[path]


def predict(model, features):
    if model.get('offsets') != list(OFFSETS):
        raise ValueError('Unknown boosted temporal layout')
    return decode(model, probabilities(load_booster(model['booster_ubj']), features))
