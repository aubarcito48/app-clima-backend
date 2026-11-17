"""Same frozen RF and PCM on both sides, different image-only policies."""
import argparse
import copy
import json
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
for name in ['source','policy','frontend','output']:p.add_argument('--'+name,type=Path,required=True)
args=p.parse_args()
data=json.loads((args.source/'comparison.json').read_text(encoding='utf8'))
data.pop('metrics',None)
data['models']={'previous':'Actual · Random Forest','balanced':'Revisión visual · Random Forest'}
data['reviewFolder']='skills-audit-v1'
data['visualPolicies']={'baseline':{'catalogs':{},'ranges':{}},'automatic':{'catalogs':{},'ranges':{}}}
policy=json.loads((args.policy/'policy.json').read_text())
source=args.frontend/'src/app/shared/isabel'
oldranges=json.loads((source/'isa-speech-ranges.json').read_text())
for language,suffix in [('es',''),('en','-en')]:
    data['visualPolicies']['baseline']['catalogs'][language]=json.loads((source/f'isa-speech-selection{suffix}.json').read_text())
    data['visualPolicies']['automatic']['catalogs'][language]=json.loads((args.policy/f'catalog-{language}.json').read_text())
    data['visualPolicies']['baseline']['ranges'][language]=oldranges[language]
    data['visualPolicies']['automatic']['ranges'][language]=policy['languages'][language]['selected_range']
    if language=='en':
        chosen=policy['languages'][language]['selected_seam'];old=policy['languages'][language]['original_seam']
        data['visualPolicies']['automatic']['catalogs'][language]['reviewedLoop']={
            **data['visualPolicies']['automatic']['ranges'][language],
            'face':chosen['face'],'velocity':chosen['velocity'],'maxFace':old['face'],'maxVelocity':old['velocity']}
for case in data['cases']:
    variant=case['automatic']
    rf=copy.deepcopy(variant['model_cues']['previous'])
    variant['model_cues']={'previous':rf,'balanced':copy.deepcopy(rf)}
    variant['cues']=rf
    case['baseline']=copy.deepcopy(variant)
    case['baseline']['forcedModel']='previous';variant['forcedModel']='balanced'
    assert case['baseline']['audio']==variant['audio']
    assert case['baseline']['sha256_pcm']==variant['sha256_pcm']
args.output.mkdir(parents=True,exist_ok=True)
(args.output/'comparison.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
