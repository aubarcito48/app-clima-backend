"""Own regularized temporal linear classifier with optional sequence decoding."""

import numpy as np

from classifier import SHAPES

VERSION = 'isa-context-ridge-v1'
NONLINEAR_VERSION = 'isa-context-rff-v1'
OFFSETS = (-4, -2, 0, 2, 4)


def context(features):
    features = np.asarray(features, dtype=float)
    if features.ndim != 2 or not len(features) or not np.isfinite(features).all():
        raise ValueError('Invalid acoustic features')
    # Call separately per recording: never concatenate neighbouring files first.
    indices = np.arange(len(features))
    return np.concatenate([features[np.clip(indices + offset, 0, len(features) - 1)]
                           for offset in OFFSETS], axis=1)


def balance_weights(indices, classes, balance, cap=None):
    if not 0 <= balance <= 1 or cap is not None and (not np.isfinite(cap) or cap < 1):
        raise ValueError('Invalid balancing parameters')
    counts = np.bincount(indices, minlength=classes)
    if not len(indices) or np.any(counts == 0):
        raise ValueError('Every model class needs training examples')
    weights = (len(indices) / (classes * counts[indices])) ** balance
    if cap is not None:
        weights = np.minimum(weights, cap)
        weights /= weights.mean()  # Keep regularization comparable between sweeps.
    return weights


def fit(recordings, *, ridge=10., balance=.5, weight_cap=None, nonlinear_scale=None):
    if not recordings or ridge <= 0 or not 0 <= balance <= 1:
        raise ValueError('Invalid temporal training configuration')
    for row in recordings:
        if len(row['features']) != len(row['labels']) or any(c not in SHAPES for c in row['labels']):
            raise ValueError('Invalid temporal labels')
    features = np.concatenate([context(row['features']) for row in recordings])
    labels = np.concatenate([row['labels'] for row in recordings])
    classes = sorted(set(labels.tolist()))
    indices = np.array([classes.index(c) for c in labels])
    counts = np.bincount(indices, minlength=len(classes))
    mean, scale = features.mean(axis=0), np.maximum(features.std(axis=0), .05)
    values = np.clip((features - mean) / scale, -8, 8)
    nonlinear = None
    if nonlinear_scale is not None:
        if not np.isfinite(nonlinear_scale) or nonlinear_scale <= 0:
            raise ValueError('Invalid nonlinear feature scale')
        rng = np.random.default_rng(20261116)
        projection = rng.normal(0, nonlinear_scale / np.sqrt(values.shape[1]), (values.shape[1], 128))
        phase = rng.uniform(0, 2 * np.pi, 128)
        hidden = np.cos(values @ projection + phase)
        hidden_mean, hidden_scale = hidden.mean(axis=0), np.maximum(hidden.std(axis=0), .05)
        values = np.column_stack([values, (hidden - hidden_mean) / hidden_scale])
        nonlinear = {'scale': nonlinear_scale, 'projection': projection.tolist(), 'phase': phase.tolist(),
                     'mean': hidden_mean.tolist(), 'std': hidden_scale.tolist(), 'seed': 20261116}
    x = np.column_stack([values, np.ones(len(features))])
    targets = np.eye(len(classes))[indices]
    weights = balance_weights(indices, len(classes), balance, weight_cap)
    focused = any('loss_weights' in row for row in recordings)
    if focused:
        focus_rows = []
        for row in recordings:
            focus = np.asarray(row.get('loss_weights', np.ones(len(row['labels']))), dtype=float)
            if focus.shape != (len(row['labels']),) or not np.isfinite(focus).all() or np.any(focus <= 0):
                raise ValueError('Invalid per-window training focus')
            focus_rows.append(focus)
        weights *= np.concatenate(focus_rows)
        weights /= weights.mean()
    penalty = np.eye(x.shape[1]) * ridge
    penalty[-1, -1] = 1e-6
    coefficients = np.linalg.solve(x.T @ (x * weights[:, None]) + penalty,
                                   x.T @ (targets * weights[:, None]))
    transitions = np.ones((len(classes), len(classes)))
    for row in recordings:
        codes = np.array([classes.index(c) for c in row['labels']])
        np.add.at(transitions, (codes[:-1], codes[1:]), 1)
    transitions /= transitions.sum(axis=1, keepdims=True)
    return {'version': NONLINEAR_VERSION if nonlinear else VERSION,
            'nonlinear': nonlinear, 'classes': classes, 'offsets': list(OFFSETS),
            'mean': mean.tolist(), 'scale': scale.tolist(), 'weights': coefficients.tolist(),
            'log_transitions': np.log(transitions).tolist(), 'transition_strength': 0.,
            'ridge': ridge, 'balance': balance, 'weight_cap': weight_cap,
            'per_window_focus': focused,
            'weight_range': [float(weights.min()), float(weights.max())],
            'counts': dict(zip(classes, counts.tolist()))}


def predict(model, features):
    if model['version'] == 'isa-small-tdnn-phonemes-v1':
        from neural_temporal import predict as predict_neural
        return predict_neural(model, features)
    if model['version'] == 'isa-random-forest-phonemes-v1':
        from forest_classifier import predict as predict_forest
        return predict_forest(model, features)
    if model['version'] == 'isa-boosted-phonemes-v1':
        from boosted_classifier import predict as predict_boosted
        return predict_boosted(model, features)
    if model['version'] not in (VERSION, NONLINEAR_VERSION) or model['offsets'] != list(OFFSETS):
        raise ValueError('Unknown temporal model')
    values = np.clip((context(features) - np.array(model['mean'])) / np.array(model['scale']), -8, 8)
    if model['version'] == NONLINEAR_VERSION:
        nonlinear = model['nonlinear']
        hidden = np.cos(values @ np.array(nonlinear['projection']) + np.array(nonlinear['phase']))
        values = np.column_stack([values, (hidden - np.array(nonlinear['mean'])) / np.array(nonlinear['std'])])
    x = np.column_stack([values, np.ones(len(values))])
    scores = x @ np.array(model['weights'])
    strength = model['transition_strength']
    if not strength:
        return np.array(model['classes'])[scores.argmax(axis=1)]
    transition = np.array(model['log_transitions']) * strength
    back = np.zeros(scores.shape, dtype=np.int32)
    previous = scores[0]
    for index in range(1, len(scores)):
        paths = previous[:, None] + transition
        back[index] = paths.argmax(axis=0)
        previous = scores[index] + paths.max(axis=0)
    path = np.empty(len(scores), dtype=int)
    path[-1] = previous.argmax()
    for index in range(len(scores) - 1, 0, -1):
        path[index - 1] = back[index, path[index]]
    return np.array(model['classes'])[path]
