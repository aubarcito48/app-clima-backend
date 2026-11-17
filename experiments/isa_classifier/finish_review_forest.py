"""Reproducible evaluation/viewers after both RF models have been frozen."""
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
S=Path(__file__).parent
BASE=ROOT/'tmp/isa-own-classifier'
MODEL=BASE/'forest-review-v2'
CORPUS=BASE/'corpus-review-v2/corpus.json'
PRIOR=BASE/'forest-v1'
POLICY=BASE/'visual-policy-v1'
FRONT=ROOT.parent/'app-clima'
RATE=BASE/'forest-rate-review-v2'
DIRECT=BASE/'forest-direct-review-v2'
VISUAL=BASE/'forest-visual-review-v2'

def py(script,*args):
    subprocess.run([sys.executable,'-X','utf8',str(S/script),*map(str,args)],cwd=ROOT,check=True)

def node(script,*args):
    subprocess.run(['node',str(S/script),*map(str,args)],cwd=ROOT,check=True)

def main():
    start=time.monotonic()
    while not (MODEL/'evaluation.json').exists():
        if time.monotonic()-start>2400:raise TimeoutError('Training incomplete')
        time.sleep(2)
    py('evaluate_pause_roles.py','--corpus',CORPUS,'--new',MODEL,'--previous',PRIOR,'--output',MODEL/'pause-roles.json')
    py('prepare_rate_balance_review.py','--source',BASE/'automatic-rate-v2','--models',MODEL,
       '--previous-models',PRIOR,'--output',RATE,'--corpus',CORPUS,
       '--model-label','Random Forest V2','--evaluation',MODEL/'evaluation.json',
       '--verified-pauses','--pause-roles',MODEL/'pause-roles.json')
    py('prepare_forest_direct.py','--source',RATE,'--output',DIRECT,
       '--previous-label','Random Forest V1','--new-label','Random Forest V2',
       '--direct-folder',DIRECT.name)
    for folder in (RATE,DIRECT):
        py('attach_reviewed_catalogs.py','--folder',folder,'--policy',POLICY)
        node('build_auto_rate_demo.mjs',FRONT,folder)
    py('prepare_timing_policy.py','--corpus',CORPUS,'--models',MODEL,'--reference',PRIOR,
       '--output',VISUAL,'--fresh-test-only','--verified-pauses')
    node('check_visual_batch.mjs',FRONT,VISUAL,POLICY)
    node('check_auto_rate_demo.mjs',FRONT,RATE)
    node('check_forest_direct.mjs',FRONT,DIRECT)
    print(json.dumps({'stage':'review_complete','direct':str(DIRECT/'index.html'),
                      'rate':str(RATE/'index.html')}),flush=True)

if __name__=='__main__':main()
