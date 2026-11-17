"""Portable Random Forest arrays: no pickle or sklearn required for inference."""
import base64
import io
from functools import lru_cache
import numpy as np
from boosted_classifier import tree_context, decode
from temporal import OFFSETS

VERSION = 'isa-random-forest-phonemes-v1'


def export_forest(forest):
    roots, left, right, feature, threshold, probability = [], [], [], [], [], []
    offset = 0
    for estimator in forest.estimators_:
        tree = estimator.tree_
        roots.append(offset)
        left.append(np.where(tree.children_left >= 0, tree.children_left+offset, -1))
        right.append(np.where(tree.children_right >= 0, tree.children_right+offset, -1))
        feature.append(tree.feature)
        threshold.append(tree.threshold)
        values = tree.value[:, 0, :]
        probability.append(values/values.sum(axis=1, keepdims=True))
        offset += tree.node_count
    output = io.BytesIO()
    np.savez_compressed(output, roots=np.array(roots), left=np.concatenate(left), right=np.concatenate(right),
        feature=np.concatenate(feature), threshold=np.concatenate(threshold), probability=np.concatenate(probability))
    return base64.b64encode(output.getvalue()).decode()


@lru_cache(maxsize=2)
def load_forest(encoded):
    with np.load(io.BytesIO(base64.b64decode(encoded, validate=True)), allow_pickle=False) as data:
        result = {key: data[key] for key in ('roots', 'left', 'right', 'feature', 'threshold', 'probability')}
    n = len(result['left']); index = np.arange(n)
    left, right, feature, roots = [result[k] for k in ('left', 'right', 'feature', 'roots')]
    if (not n or n > 2_000_000 or not 1 <= len(roots) <= 512 or roots[0] != 0
            or np.any(np.diff(roots) <= 0) or np.any(roots >= n)
            or any(result[k].shape != (n,) for k in ('right', 'feature', 'threshold'))
            or any(result[k].dtype.kind not in 'iu' for k in ('roots', 'left', 'right', 'feature'))
            or np.any((left >= 0) != (right >= 0))
            or np.any((left >= 0) & ((left <= index) | (left >= n) | (right <= index) | (right >= n) | (feature < 0)))
            or result['probability'].ndim != 2 or result['probability'].shape[0] != n
            or not np.isfinite(result['threshold']).all() or not np.isfinite(result['probability']).all()
            or np.any(result['probability'] < 0) or not np.allclose(result['probability'].sum(axis=1), 1)):
        raise ValueError('Invalid portable forest')
    return result


def probabilities_from_arrays(arrays, context, maximum_depth):
    values = np.asarray(context, dtype=np.float32)
    n = len(values)
    output = np.zeros((n, arrays['probability'].shape[1]))
    for root in arrays['roots']:
        nodes = np.full(n, root, dtype=int)
        for _ in range(maximum_depth+1):
            active = np.flatnonzero(arrays['left'][nodes] >= 0)
            if not len(active): break
            features = arrays['feature'][nodes[active]]
            if np.any(features >= values.shape[1]): raise ValueError('Forest feature layout changed')
            go_left = values[active, features] <= arrays['threshold'][nodes[active]]
            nodes[active] = np.where(go_left, arrays['left'][nodes[active]], arrays['right'][nodes[active]])
        if np.any(arrays['left'][nodes] >= 0): raise ValueError('Forest depth metadata changed')
        output += arrays['probability'][nodes]
    return output/len(arrays['roots'])


def predict(model, features):
    if model.get('offsets') != list(OFFSETS): raise ValueError('Forest temporal layout changed')
    depth = model['max_depth']
    if not isinstance(depth, int) or not 1 <= depth <= 128: raise ValueError('Invalid forest depth')
    return decode(model, probabilities_from_arrays(load_forest(model['forest_npz']), tree_context(features), depth))
