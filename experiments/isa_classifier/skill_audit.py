"""Read-only sample/atlas audit through installed audio and facial skills."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import hashlib
from PIL import Image
from classifier import read_recording

SKILLS = Path('C:/Users/rocii/.codex/skills')
MEDIA = Path('C:/Users/rocii/.codex/skill-runtimes/isa-media')


def extract(frontend, output):
    source = frontend/'src/app/shared/isabel'
    rows = []
    ranges = json.loads((source/'isa-speech-ranges.json').read_text())
    for language, suffix in [('es',''),('en','-en')]:
        manifest = json.loads((source/f'isa-speech-manifest{suffix}.json').read_text())
        catalog = json.loads((source/f'isa-speech-selection{suffix}.json').read_text())
        folder = output/'frames'/language
        folder.mkdir(parents=True,exist_ok=True)
        pages = {}
        for index, original in enumerate(manifest['sourceFrames']):
            page = next(p for p in manifest['pages'] if p['first'] <= index < p['first']+p['count'])
            path = frontend/'public'/page['image']
            if page['image'] not in pages:
                pages[page['image']] = Image.open(path).convert('RGB')
            local = index-page['first']
            w,h,c = manifest['width'],manifest['height'],manifest['columns']
            x,y = local%c*w,local//c*h
            frame = pages[page['image']].crop((x,y,x+w,y+h))
            target = folder/f'frame-{index:03}.png'
            frame.save(target)
            anchor = min(range(len(catalog['candidates'])),key=lambda i:abs(index-catalog['candidates'][i]))
            rows.append({'language':language,'index':index,'original_video_frame':original,
                'file':str(target.relative_to(output)).replace('\\','/'),
                'in_speech_range':ranges[language]['first']<=index<ranges[language]['end'],
                'provisional_label':catalog['labels'][anchor],
                'is_anchor': index in catalog['candidates'],
                'sha256_image':hashlib.sha256(target.read_bytes()).hexdigest()})
        for page in pages.values(): page.close()
    (output/'frame-index.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
    print(json.dumps({'extracted':len(rows),'original_atlases_preserved':True}),flush=True)


def audio(corpus, output):
    manifest = json.loads(corpus.read_text(encoding='utf8'))
    rows = [r for r in manifest['recordings'] if r['split']=='test' and r.get('evaluation')=='fresh']
    reports = []
    env = {**os.environ, 'PATH':str(MEDIA/'bin')+os.pathsep+os.environ['PATH'], 'PYTHONIOENCODING':'utf-8'}
    for row in rows:
        wav = corpus.parent/row['file']
        if read_recording(wav)[3] != row['sha256_pcm']: raise ValueError('Audio changed')
        folder = output/'audio'/row['id']
        folder.mkdir(parents=True,exist_ok=True)
        args = ['node',str(SKILLS/'audio-lens/bin/audio-lens.js'),'analyze',str(wav),
                '--clips','--peak','--rms','--silence-ratio']
        representative = row['group_id'].endswith(('-01','-02'))
        if representative: args += ['--spectrogram',str(folder/'spectrogram.png')]
        result = subprocess.run(args,check=True,capture_output=True,text=True,encoding='utf8')
        measured = json.loads(result.stdout)
        (folder/'audio-lens.json').write_text(json.dumps(measured,indent=2),encoding='utf8')
        if representative:
            transcript = folder/'transcript.txt'
            transcript.write_text(row['text'],encoding='utf8')
            result = subprocess.run([str(MEDIA/'Scripts/python.exe'),str(SKILLS/'prosody-lens/scripts/prosody_analyze.py'),
                str(wav),'--out-dir',str(folder/'prosody'),'--transcript',str(transcript),
                '--speaker',row['language'],'--goal','inspect pacing and pauses',
                '--take-label',row['variant'],'--memo-type','synthetic weather advice'],
                check=True,capture_output=True,text=True,encoding='utf8',env=env)
            (folder/'prosody-run.log').write_text(result.stdout+result.stderr,encoding='utf8')
        reports.append({'id':row['id'],'language':row['language'],'variant':row['variant'],
            'group_id':row['group_id'],'sha256_pcm':row['sha256_pcm'],
            'metrics':measured,'prosody':representative})
        print(json.dumps({'audio_checked':row['id'],'prosody':representative}),flush=True)
    (output/'audio-audit.json').write_text(json.dumps(reports,indent=2),encoding='utf8')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--frontend',type=Path,required=True)
    p.add_argument('--corpus',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=['extract','audio'],required=True)
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    if args.mode=='extract': extract(args.frontend,args.output)
    else: audio(args.corpus,args.output)


if __name__=='__main__': main()
