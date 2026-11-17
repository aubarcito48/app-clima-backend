"""Compare production's frozen RF inference with the trained laboratory model."""
import json
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'experiments/isa_classifier')]
from classifier import read_recording,timeline
from rhythm_features import features_for_model
import temporal
from api.services.own_lip_sync import attach_alignment,infer

def main():
    corpus=ROOT/'tmp/isa-own-classifier/corpus-review-v2'
    rows=json.loads((corpus/'corpus.json').read_text(encoding='utf8'))['recordings']
    selected=[next(r for r in rows if r['language']==l and r['split']=='test' and r.get('evaluation')=='fresh' and r['variant']==v)
              for l in ('es','en') for v in ('baseline','automatic')]
    for row in selected:
        samples,rate,_,fingerprint=read_recording(corpus/row['file'])
        info=json.loads((corpus/row['phones_file']).read_text(encoding='utf8'));info['sha256_pcm']=fingerprint
        model=json.loads((ROOT/f"tmp/isa-own-classifier/forest-review-v2/hybrid-{row['language']}.json").read_text())
        features,_,hop=features_for_model(model,samples,rate,alignment=info)
        expected=timeline(temporal.predict(model,features),hop,row['duration'])
        actual=infer(attach_alignment((corpus/row['file']).read_bytes(),info),row['language'])
        with tempfile.TemporaryDirectory() as folder:
            wav=Path(folder)/'public.wav';wav.write_bytes(actual)
            _,_,cues,pcm=read_recording(wav)
        assert cues==expected and pcm==fingerprint and b'isap' not in actual and b'isa-rf-v2' in actual
    print(json.dumps({'same_PCM':True,'same_predictions':True,'private_alignment_removed':True,'cases':len(selected)}))

if __name__=='__main__':main()
