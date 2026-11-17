"""One-clock model comparison, retaining automatic voice rate and frame pacing."""
import argparse
import copy
import json
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--new-label', default='Random Forest · pausas reparadas')
p.add_argument('--previous-label', default='XGBoost · pausas reparadas')
p.add_argument('--direct-folder', default='forest-direct-v1')
args = p.parse_args()
source = args.source/'comparison.json'
data = json.loads(source.read_text(encoding='utf8'))
data['models'] = {'balanced': args.new_label, 'previous': args.previous_label}
data['directFolder'] = args.direct_folder
data['reviewFolder'] = args.source.name
data['directComparison'] = True
source.write_text(json.dumps(data, ensure_ascii=False), encoding='utf8')
data['compareModels'] = True
for case in data['cases']:
    automatic = copy.deepcopy(case['automatic'])
    case['baseline'] = copy.deepcopy(automatic)
    case['baseline']['forcedModel'] = 'previous'
    case['automatic']['forcedModel'] = 'balanced'
args.output.mkdir(parents=True, exist_ok=True)
(args.output/'comparison.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf8')
