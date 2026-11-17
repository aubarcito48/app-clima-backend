"""Wait for the isolated corpus, check provenance/audio, fit the frozen RF grid."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from collections import Counter
from classifier import read_recording

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('corpus','previous','reference','output','audio-lens'):
        p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args()
    start=time.monotonic()
    while not args.corpus.exists():
        if time.monotonic()-start>2400:raise TimeoutError('Corpus generation incomplete')
        time.sleep(2)
    data=json.loads(args.corpus.read_text(encoding='utf8'))
    old=json.loads(args.previous.read_text(encoding='utf8'))
    previous={r['id']:r for r in old['recordings']}
    for row in data['recordings']:
        if row['id'] in previous:
            prior=previous[row['id']]
            assert (row['split'],row['sha256_pcm'],row['text'])==(prior['split'],prior['sha256_pcm'],prior['text'])
    added=[r for r in data['recordings'] if r['id'] not in previous]
    assert len({r['group_id'] for r in added})==48
    assert all(r['evaluation']=='legacy' for r in data['recordings'] if r['id'] in previous)
    args.output.mkdir(parents=True,exist_ok=True)
    def check(row):
        wav=args.corpus.parent/row['file']
        assert read_recording(wav)[3]==row['sha256_pcm']
        result=subprocess.run(['node',str(args.audio_lens),'analyze',str(wav),'--clips','--peak','--rms','--silence-ratio'],capture_output=True,text=True,check=True)
        return {'id':row['id'],'language':row['language'],**json.loads(result.stdout)}
    with ThreadPoolExecutor(max_workers=2) as workers:
        audio=list(workers.map(check,added))
    (args.output/'audio-qa.json').write_text(json.dumps(audio,indent=2),encoding='utf8')
    if any(r.get('clips') or r.get('silenceRatio',0)>=.99 for r in audio):
        raise ValueError('New corpus failed audio quality gate')
    provenance={'from_scratch':True,'training':True,'previous_rows_preserved':len(previous),
      'new_recordings':len(added),'new_groups':48,'total_recordings':len(data['recordings']),
      'split_counts':dict(Counter(r['split'] for r in data['recordings'])),
      'new_split_counts':dict(Counter(r['split'] for r in added)),
      'corpus_sha256':digest(args.corpus),
      'reference_hashes':{language:digest(args.reference/f'hybrid-{language}.json') for language in ('es','en')},
      'code_sha256':digest(Path(__file__).with_name('train_forest.py')),
      'scope':'Audio RF retraining; visual catalog/runtime fixes remain a separate layer'}
    (args.output/'run-provenance.json').write_text(json.dumps(provenance,indent=2),encoding='utf8')
    print(json.dumps({'stage':'quality_passed',**provenance}),flush=True)
    subprocess.run([sys.executable,'-X','utf8',str(Path(__file__).with_name('train_forest.py')),
      '--corpus',str(args.corpus),'--reference',str(args.reference),'--output',str(args.output),
      '--reference-label','Random Forest V1','--candidate-label','Random Forest V2'],check=True)
    assert all(digest(args.reference/f'hybrid-{language}.json')==provenance['reference_hashes'][language] for language in ('es','en'))
    print(json.dumps({'stage':'training_complete','elapsed_seconds':round(time.monotonic()-start,1)}),flush=True)

if __name__=='__main__':main()
