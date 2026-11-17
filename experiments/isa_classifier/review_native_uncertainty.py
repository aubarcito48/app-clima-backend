"""Inspect unresolved mouths at source resolution without changing any atlas."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from PIL import Image,ImageDraw,ImageFont
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--frontend',type=Path,required=True);p.add_argument('--policy',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14);rows=[]
ffmpeg='C:/Users/rocii/.codex/skill-runtimes/isa-media/bin/ffmpeg.exe'
for language,suffix in [('es',''),('en','-en')]:
 manifest=json.loads((args.frontend/f'src/app/shared/isabel/isa-speech-manifest{suffix}.json').read_text())
 catalog=json.loads((args.policy/f'catalog-{language}.json').read_text())
 indices=[i for i,s in enumerate(catalog['mouthStates']) if s=='uncertain']
 frames=[manifest['sourceFrames'][i] for i in indices]
 folder=args.output/language;folder.mkdir(exist_ok=True)
 source=args.frontend/'public/isa-bot'/manifest['source'];fingerprint=hashlib.sha256(source.read_bytes()).hexdigest()
 select='+'.join(f'eq(n\\,{i})' for i in frames)
 # Authoring crop [300,8,704,704] -> 320²; mouth ROI [115,112,195,152].
 filter=f'fps=24,select={select},crop=176:88:553:254'
 subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-y','-threads','1','-i',str(source),'-vf',filter,
                 '-filter_threads','1','-fps_mode','vfr','-start_number','0',str(folder/'%03d.png')],check=True,capture_output=True)
 assert hashlib.sha256(source.read_bytes()).hexdigest()==fingerprint
 if len(list(folder.glob('*.png')))!=len(indices):raise ValueError('Native extraction count mismatch')
 for n,(index,frame) in enumerate(zip(indices,frames)):
  rows.append({'language':language,'atlas_index':index,'video_frame':frame,'file':str((folder/f'{n:03}.png').relative_to(args.output)),
   'source_sha256':fingerprint,'state':'uncertain','note':'native-resolution inspection only; labels unchanged'})
sheet=Image.new('RGB',(8*176,((len(rows)+7)//8)*110),'#edf8fc');draw=ImageDraw.Draw(sheet)
for n,row in enumerate(rows):
 x,y=n%8*176,n//8*110;sheet.paste(Image.open(args.output/row['file']).convert('RGB'),(x,y))
 draw.text((x+4,y+89),f"{row['language']} #{row['atlas_index']} src {row['video_frame']}",font=font,fill='#123952')
sheet.save(args.output/'native-uncertain-mouths.png')
(args.output/'index.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
print(json.dumps({'native_crops':len(rows),'labels_changed':False,'originals_preserved':True}))
