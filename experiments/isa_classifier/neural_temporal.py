"""Small time-delay neural net with portable NumPy inference, no pickle."""
import numpy as np
from boosted_classifier import decode

VERSION = 'isa-small-tdnn-phonemes-v1'
OFFSETS = (-12, -8, -4, 0, 4, 8, 12)


def context(features):
    x = np.asarray(features, dtype=np.float64)
    if x.ndim != 2 or not len(x) or not np.isfinite(x).all():
        raise ValueError('Invalid neural features')
    indices = np.arange(len(x))
    return np.concatenate([x[np.clip(indices + offset, 0, len(x)-1)] for offset in OFFSETS], axis=1)


def normalize(values, mean, scale):
    mean, scale = np.asarray(mean), np.asarray(scale)
    if (mean.shape != (values.shape[1],) or scale.shape != mean.shape
            or not np.isfinite(mean).all() or not np.isfinite(scale).all() or np.any(scale <= 0)):
        raise ValueError('Invalid neural normalization')
    return np.clip((values-mean)/scale, -8, 8)


def export_network(network):
    return {'weights': [w.tolist() for w in network.coefs_],
            'biases': [b.tolist() for b in network.intercepts_]}


def probabilities_from_context(model, values):
    if model.get('offsets') != list(OFFSETS):
        raise ValueError('Unknown neural temporal layout')
    h = normalize(values, model['mean'], model['scale'])
    weights, biases = model['network']['weights'], model['network']['biases']
    if len(weights) != 3 or len(biases) != 3:
        raise ValueError('Invalid neural layer count')
    for i, (weight, bias) in enumerate(zip(weights, biases)):
        w, b = np.asarray(weight), np.asarray(bias)
        if (w.ndim != 2 or w.shape[0] != h.shape[1] or b.shape != (w.shape[1],)
                or not np.isfinite(w).all() or not np.isfinite(b).all()):
            raise ValueError('Invalid neural layer')
        h = h @ w + b
        if i < 2:
            h = np.maximum(h, 0)
    if h.shape[1] != len(model['classes']):
        raise ValueError('Neural output class mismatch')
    h -= h.max(axis=1, keepdims=True)
    p = np.exp(h)
    return p/p.sum(axis=1, keepdims=True)


def predict(model, features):
    return decode(model, probabilities_from_context(model, context(features)))
