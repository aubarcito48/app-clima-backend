"""Image-only visual review and loop search; no audio/test metric selection."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Atlas indices inspected in three 68-frame mouth contact sheets per language.
# Visible aperture is independent of the fine phonetic shape. Ambiguous puckers
# and transition frames are deliberately left uncertain. Not human gold labels.
REVIEW = {
 'es': {'closed':[(0,11),(52,54),(62,63),(80,84),(137,140),(188,203)],
        'open':[(12,51),(55,61),(65,79),(85,125),(129,136),(143,183)]},
 'en': {'closed':[(0,10),(44,46),(66,69),(82,83),(86,87),(109,111),(139,149),(184,203)],
        'open':[(11,25),(28,31),(34,43),(48,65),(70,77),(84,85),(88,99),(103,108),
                (112,126),(130,138),(150,154),(161,180)]},
}


def reviewed_states(language):
    result=['uncertain']*204
    for state, intervals in REVIEW[language].items():
        for first,last in intervals:
            for i in range(first,last+1):
                if result[i]!='uncertain': raise ValueError('Overlapping visual review')
                result[i]=state
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audit',type=Path,required=True)
    p.add_argument('--frontend',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    source=args.frontend/'src/app/shared/isabel'
    ranges=json.loads((source/'isa-speech-ranges.json').read_text())
    records=json.loads((args.audit/'frame-index.json').read_text())
    facial=[r for r in map(json.loads,(args.audit/'facial-audit.jsonl').read_text(encoding='utf8').splitlines()) if r['type']=='result']
    report={'provenance':'agent visual inspection of original atlas mouth contact sheets, not human gold',
            'selection':'image-only fixed constraints; no audio test scoring','languages':{}}
    for language,suffix in [('es',''),('en','-en')]:
        catalog=json.loads((source/f'isa-speech-selection{suffix}.json').read_text())
        states=reviewed_states(language)
        images={}
        evidence=[]
        for row in [r for r in records if r['language']==language]:
            path=args.audit/row['file']
            if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256_image']:
                raise ValueError('Changed reviewed image')
            images[row['index']]=np.asarray(Image.open(path).convert('RGB'),float)/255
            evidence.append({**row,'mouth_state':states[row['index']],
                'review_source':'agent-visual-review' if states[row['index']]!='uncertain' else 'unresolved'})
        new={**catalog,'mouthStates':states,'reviewProvenance':report['provenance']}
        review_font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14)
        for start in range(0,204,68):
            sheet=Image.new('RGB',(960,765),'#edf8fc');draw=ImageDraw.Draw(sheet)
            for n,i in enumerate(range(start,min(start+68,204))):
                im=Image.fromarray((images[i]*255).astype('uint8'))
                x,y=n%8*120,n//8*85
                sheet.paste(im.crop((115,112,195,152)).resize((120,60)),(x,y))
                draw.text((x+4,y+62),str(i),font=review_font,fill='#123952')
            sheet.save(args.output/f'mouths-{language}-{start}.png')
        (args.output/f'catalog-{language}.json').write_text(json.dumps(new),encoding='utf8')
        candidates=[]
        if language=='en':
            face={int(Path(r['path']).stem.split('-')[-1]):r['faces'][0] for r in facial if Path(r['path']).parent.name==language}
            def region(i):
                a=images[i][65:160,100:205].copy()
                a[46:86,20:90]=0
                return a
            roi={i:region(i) for i in images}
            def measures(last,first):
                pose=float(np.abs(roi[last]-roi[first]).mean())
                velocity=float(np.abs((roi[last]-roi[last-1])-(roi[first+1]-roi[first])).mean())
                return {'face':pose,'velocity':velocity,'score':pose+.25*velocity}
            original=measures(ranges['en']['end']-1,ranges['en']['first'])
            # Preserve >=6 seconds of the original forward track. Avoid the idle
            # tail and new seams through blinks or incompatible mouth states.
            for first in range(8,33):
                for last in range(max(first+143,160),185):
                    if states[first]!=states[last] or states[first]=='uncertain':continue
                    if any(face[i]['state']!='open' for i in [last-1,last,first,first+1]):continue
                    if abs(face[last]['jaw_open']-face[first]['jaw_open'])>.02:continue
                    metric=measures(last,first)
                    if metric['face']>=original['face'] or metric['velocity']>original['velocity']:continue
                    candidates.append({'first':first,'end':last+1,'duration':(last+1-first)/24,**metric})
            candidates.sort(key=lambda r:(r['score'],-r['duration']))
            if not candidates: raise ValueError('No seam improves pose and velocity under fixed constraints')
            chosen=candidates[0]
            selected={'first':chosen['first'],'end':chosen['end']}
            font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14)
            pairs=[('original',ranges['en']['end']-1,ranges['en']['first'])]+[(str(i+1),r['end']-1,r['first']) for i,r in enumerate(candidates[:5])]
            sheet=Image.new('RGB',(6*160,6*185),'#edf8fc');draw=ImageDraw.Draw(sheet)
            for row,(label,last,first) in enumerate(pairs):
                indices=[last-2,last-1,last,first,first+1,first+2]
                for col,i in enumerate(indices):
                    im=Image.fromarray((images[i]*255).astype('uint8')).resize((160,160))
                    sheet.paste(im,(col*160,row*185))
                    draw.text((col*160+3,row*185+162),f'{label} #{i}',font=font,fill='#123952')
            sheet.save(args.output/'seam-candidates-en.png')
        else:
            original=None; chosen=None; selected=ranges['es']
        (args.output/f'review-{language}.json').write_text(json.dumps({'provenance':report['provenance'],'frames':evidence},indent=2),encoding='utf8')
        report['languages'][language]={'states':{s:states.count(s) for s in ['open','closed','uncertain']},
            'original_range':ranges[language],'selected_range':selected,'original_seam':original,
            'selected_seam':chosen,'candidates':candidates}
    (args.output/'policy.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps({l:{k:v for k,v in r.items() if k!='candidates'} for l,r in report['languages'].items()}))


if __name__=='__main__':main()
