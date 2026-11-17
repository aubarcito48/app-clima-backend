"""Measured survey of skills outputs; candidate visual mismatches, not new labels."""
import argparse
from collections import Counter
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def stats(values):
    a=np.array(values,float)
    return {'min':float(a.min()),'median':float(np.median(a)),'p95':float(np.quantile(a,.95)),'max':float(a.max())}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('folder',type=Path); p.add_argument('frontend',type=Path)
    args=p.parse_args(); root=args.folder; source=args.frontend/'src/app/shared/isabel'
    faces=[r for r in map(json.loads,(root/'facial-audit.jsonl').read_text(encoding='utf8').splitlines()) if r['type']=='result']
    audios=json.loads((root/'audio-audit.json').read_text())
    paths=json.loads((root/'animation-paths.json').read_text())
    summary={'scope':{'audios':len(audios),'prosody_reports':sum(r['prosody'] for r in audios),'frames':len(faces),'animation_plans':len(paths)},'languages':{}}
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14)
    for language,suffix in [('es',''),('en','-en')]:
        rows=[r for r in faces if Path(r['path']).parent.name==language]
        byindex={int(Path(r['path']).stem.split('-')[-1]):r for r in rows}
        catalog=json.loads((source/f'isa-speech-selection{suffix}.json').read_text())
        ranges=json.loads((source/'isa-speech-ranges.json').read_text())[language]
        labels={i:catalog['labels'][min(range(len(catalog['candidates'])),key=lambda j:abs(i-catalog['candidates'][j]))] for i in byindex}
        images={i:np.asarray(Image.open(r['path']).convert('RGB'),float)/255 for i,r in byindex.items()}
        # Face-focused photometric changes, not optical flow or accuracy.
        def change(a,b):
            delta=np.abs(images[a]-images[b])[65:160,100:205].copy()
            delta[46:86,20:90]=0 # exclude fixed mouth ROI [120,111,190,151]
            return float(delta.mean())
        first,end=ranges['first'],ranges['end']
        adjacent=[change(i,i+1) for i in range(first,end-1)]
        seam=change(end-1,first)
        xframes=[i for i,l in labels.items() if l=='X']
        oframes=[i for i,l in labels.items() if l!='X']
        selected=list(dict.fromkeys([first,end-1,0,203,
            *sorted(xframes,key=lambda i:byindex[i]['faces'][0]['jaw_open'],reverse=True)[:3],
            *sorted(oframes,key=lambda i:byindex[i]['faces'][0]['jaw_open'])[:3],
            *sorted(byindex,key=lambda i:byindex[i]['faces'][0]['jaw_open'],reverse=True)[:3],
            *[i for i,r in byindex.items() if r['status']=='closed'][:3]]))
        sheet=Image.new('RGB',(4*210,((len(selected)+3)//4)*270),'#edf8fc')
        draw=ImageDraw.Draw(sheet)
        for n,i in enumerate(selected):
            x,y=n%4*210,n//4*270
            frame=Image.open(byindex[i]['path']).convert('RGB')
            sheet.paste(frame.resize((180,180)),(x+15,y))
            sheet.paste(frame.crop((120,111,190,151)).resize((175,60)),(x+17,y+180))
            draw.text((x+8,y+241),f"{language} #{i} label {labels[i]} jaw {byindex[i]['faces'][0]['jaw_open']:.3f}",font=font,fill='#123952')
        sheet.save(root/f'frame-contact-{language}.png')
        audio=[r for r in audios if r['language']==language]
        plans=[r for r in paths if r['language']==language]
        audio_by_id={r['id']:r for r in audio}
        rate={}
        for variant in ['baseline','automatic']:
            subset=[r for r in plans if r['version']=='previous' and audio_by_id[r['id']]['variant']==variant]
            rate[variant]={'advice_wps':stats([r['timing']['advice_words_per_second'] for r in subset]),
                           'advice_segment_wps':stats([s['words_per_second'] for r in subset for s in r['timing']['segments'] if s['role']=='advice'])}
        facial={'status_counts':dict(Counter(r['status'] for r in rows)),
            'jaw_open':stats([r['faces'][0]['jaw_open'] for r in rows]),
            'flags':{key:sum(r['image_quality'][key] for r in rows) for key in ['blurry','overexposed','underexposed']},
            'pose':{key:stats([r['faces'][0][key] for r in rows]) for key in ['head_pitch_deg','head_yaw_deg','head_roll_deg']},
            'cycle':{'first':first,'last':end-1,'duration_seconds':(end-first)/24,
                'adjacent_face_change':stats(adjacent),'seam_face_change':seam,'seam_vs_adjacent_p95':seam/np.quantile(adjacent,.95)},
            'contact_frames':selected,'label_note':catalog.get('labelNote','provisional labels')}
        closed_runs=[]
        for i in sorted(byindex):
            if byindex[i]['status']!='closed': continue
            if closed_runs and i==closed_runs[-1][-1]+1: closed_runs[-1].append(i)
            else: closed_runs.append([i])
        facial['blink_candidates']=[{'first':g[0],'last':g[-1],'duration_ms':len(g)/24*1000} for g in closed_runs]
        animation={}
        for version in ['previous','boosted']:
            subset=[r for r in plans if r['version']==version]
            distances=[change(a,b) for r in subset for a,b in zip(r['frames'],r['frames'][1:])]
            seams=[{'id':r['id'],**s,'face_change':change(s['from'],s['to'])} for r in subset for s in r['seams']]
            animation[version]={'name':'Random Forest' if version=='previous' else 'TDNN',
                'face_changes':stats(distances),'seams':seams,'seam_count':len(seams)}
        available=matched=count=0
        drift=4 if language=='es' else 6
        for row in plans:
            if row['version']!='previous': continue
            for i,(frame,wanted) in enumerate(zip(row['frames'],row['wanted'])):
                t=(i+.5)/24
                if wanted=='X' or not any(a<=t<b for a,b in row['advice_spans']): continue
                count+=1
                possible={row['provisionalShapes'][first+(i+offset)%(end-first)] for offset in range(-drift,drift+1)}
                available+=wanted in possible
                matched+=row['provisionalShapes'][frame]==wanted
        animation['rf_requested_shape_availability']={'note':'provisional visual labels; non-rest advice instants; optimistic independent-window availability, ignores path constraints; not classifier accuracy',
            'instants':count,'shape_available':available,'shape_available_ratio':available/count,
            'selected_shape_matches':matched,'selected_shape_match_ratio':matched/count,'max_drift_frames':drift}
        summary['languages'][language]={'audio':{'peak_db':stats([r['metrics']['peakDb'] for r in audio]),
            'mean_rms_db':stats([r['metrics']['meanRms'] for r in audio]),
            'silence_ratio_at_minus60db':stats([r['metrics']['silenceRatio'] for r in audio]),
            'clipped_samples':sum(r['metrics']['clipped'] for r in audio),'rate':rate},'facial':facial,'animation':animation}
    (root/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    print(json.dumps({language:{'rate':r['audio']['rate'],'cycle':r['facial']['cycle'],
        'seams':{k:v['seam_count'] for k,v in r['animation'].items() if 'seam_count' in v}} for language,r in summary['languages'].items()}))


if __name__=='__main__': main()
