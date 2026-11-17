"""Paired uncertainty summary over held-out phrase groups, not audio windows."""
import json
from pathlib import Path
import sys
import numpy as np

folder = Path(sys.argv[1])
report = json.loads((folder / 'evaluation.json').read_text(encoding='utf8'))
result = {}
for language, data in report['languages'].items():
    new, previous = data['boosted']['grouped_advice'], data['identity']['grouped_advice']
    if set(new['groups']) != set(previous['groups']):
        raise ValueError('Models were evaluated on different phrase groups')
    rng = np.random.default_rng(20261116)
    comparisons = {}
    for metric in ('frame_agreement', 'macro_f1'):
        delta = np.array([new['groups'][key][metric] - previous['groups'][key][metric] for key in new['groups']])
        draws = rng.choice(delta, size=(10000, len(delta)), replace=True).mean(axis=1) * 100
        comparisons[metric] = {'delta_percentage_points': float(delta.mean() * 100),
            'paired_bootstrap_95_percent': np.quantile(draws, [.025, .975]).tolist(),
            'phrase_groups': len(delta), 'improved_groups': int(np.sum(delta > 0))}
    result[language] = comparisons
(folder / 'paired-comparison.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result))
