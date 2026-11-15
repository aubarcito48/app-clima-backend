"""Isolated Piper voice comparison; downloads data only, no app/env changes or Groq."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
import wave

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'tmp/isa-english-candidates'
REVISION='e9ab671f2a0e50a701b34361136ba3e6a3a9eb0c'
TEXT='Wear a light jacket. It may rain later; bring an umbrella.'
ASSETS={
 'cori':('en/en_GB/cori/medium','en_GB-cori-medium',
   ('2e0a55e140de672aa19b182602b407607bd2e6c35fc6020c0b1516053c02e995','e15ce88851dd5f09d140eb390d3d22cbec0179dc','8c00fba175b469a11c0e7cceccbebb8209f93a2a'),(63221984,5471,1171)),
 'amy':('en/en_US/amy/medium','en_US-amy-medium',
   ('cf9ccdec59f05adee47173f6fb4d89e8b0c5f30c178748d2572fe4efd1d2724c','001482532b3ef98cca71ebb5b09384062bf4d737','50f8779dcf71218aa2b7d483aae28a473a66edf3'),(63221984,5465,461)),
}

def matches(path,size,digest,lfs):
    if not path.is_file() or path.stat().st_size!=size:return False
    raw=path.read_bytes()
    actual=hashlib.sha256(raw).hexdigest() if lfs else hashlib.sha1(f'blob {size}\0'.encode()+raw).hexdigest()
    return actual==digest

def download():
    for key,(remote,name,digests,sizes) in ASSETS.items():
        folder=FOLDER/'models'/key;folder.mkdir(parents=True,exist_ok=True)
        for i,filename in enumerate((name+'.onnx',name+'.onnx.json','MODEL_CARD')):
            target=folder/filename
            if matches(target,sizes[i],digests[i],i==0):continue
            partial=target.with_suffix(target.suffix+'.partial')
            url=f'https://huggingface.co/rhasspy/piper-voices/resolve/{REVISION}/{remote}/{filename}'
            with urllib.request.urlopen(url,timeout=30) as response,partial.open('wb') as output:
                total=0
                while chunk:=response.read(1024*1024):
                    total+=len(chunk)
                    if total>sizes[i]:raise ValueError('Unexpected asset size')
                    output.write(chunk)
            if not matches(partial,sizes[i],digests[i],i==0):raise ValueError('Asset hash mismatch')
            partial.replace(target)
        print(f'{key}: pinned model/config/card verified',flush=True)

def worker(key,scale,output):
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
    sys.path.insert(0,str(ROOT))
    import numpy as np
    import onnxruntime as rt
    from piper import PiperVoice,SynthesisConfig
    from piper.config import PiperConfig
    from api.services.voice_chunks import prepare_voice_chunks
    if key in ASSETS:
        _,name,_,_=ASSETS[key];model=FOLDER/'models'/key/(name+'.onnx')
    else:model=ROOT/'models/piper-sharvard/en_US-lessac-medium.onnx'
    config=PiperConfig.from_dict(json.loads(model.with_suffix('.onnx.json').read_text(encoding='utf8')))
    if config.sample_rate!=22050 or config.num_speakers!=1:raise ValueError('Unexpected voice config')
    options=rt.SessionOptions();options.intra_op_num_threads=options.inter_op_num_threads=1
    options.execution_mode=rt.ExecutionMode.ORT_SEQUENTIAL
    options.enable_cpu_mem_arena=False;options.enable_mem_pattern=False
    options.add_session_config_entry('session.disable_prepacking','1')
    voice=PiperVoice(session=rt.InferenceSession(str(model),sess_options=options,providers=['CPUExecutionProvider']),config=config)
    synthesis=SynthesisConfig(speaker_id=0,length_scale=config.length_scale*scale)
    chunks=prepare_voice_chunks(voice,TEXT,'en');previous=[]
    with wave.open(str(output),'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(22050)
        for chunk in chunks:
            samples=voice.phoneme_ids_to_audio(voice.phonemes_to_ids(chunk),synthesis)
            if not np.isfinite(samples).all():raise ValueError('Invalid audio')
            if previous:wav.writeframesraw(bytes(22050*(80 if previous[-1] in '.!?;:' else 20)//1000*2))
            wav.writeframesraw((np.clip(samples,-1,1)*32767).astype('<i2').tobytes());previous=chunk

def run():
    sys.path.insert(0,str(ROOT))
    from api.services.lip_sync import add_lip_sync
    FOLDER.mkdir(parents=True,exist_ok=True)
    binary=ROOT/'models/rhubarb/runtime/rhubarb.exe'
    if not binary.is_file():
        binaries=list((ROOT/'models/rhubarb').rglob('rhubarb.exe'))
        if len(binaries)!=1:raise ValueError('Local Rhubarb binary missing')
        binary=binaries[0]
    records=[]
    for key,scale in (('lessac',1),('cori',1),('cori',1.08),('amy',1),('amy',1.08)):
        identifier=f'{key}-{str(scale).replace(".","_")}';raw=FOLDER/(identifier+'-raw.wav');output=FOLDER/(identifier+'.wav')
        if not output.is_file():
            completed=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker',key,'--scale',str(scale),'--output',str(raw)],capture_output=True,timeout=45)
            if completed.returncode:raise RuntimeError(f'{identifier}: synthesis failed')
            audio=add_lip_sync(raw.read_bytes(),binary,timeout=60)
            if b'isav' not in audio:raise RuntimeError(f'{identifier}: missing Rhubarb cues')
            output.write_bytes(audio)
        with wave.open(str(output),'rb') as wav:duration=wav.getnframes()/wav.getframerate()
        record={'id':identifier,'voice':key,'lengthScaleMultiplier':scale,'duration':duration,'file':output.name,
                'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'text':TEXT,'reviewed':False}
        records.append(record);print(json.dumps(record),flush=True)
    (FOLDER/'report.json').write_text(json.dumps({'revision':REVISION,'text':TEXT,'reviewed':False,'cases':records},indent=2),encoding='utf8')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--download',action='store_true')
    parser.add_argument('--worker',choices=('lessac','cori','amy'));parser.add_argument('--scale',type=float,default=1)
    parser.add_argument('--output',type=Path);args=parser.parse_args()
    if args.worker:
        if args.scale not in (1,1.08) or args.output is None or not args.output.resolve().is_relative_to(FOLDER.resolve()):parser.error('Invalid isolated worker arguments')
        worker(args.worker,args.scale,args.output)
    elif args.download:download()
    else:run()
