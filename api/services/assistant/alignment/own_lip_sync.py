"""Private synthesis alignment transport and bounded RF V2 inference."""
import io
import json
import struct
import subprocess
import sys
import wave
from pathlib import Path
from api.services.assistant.alignment.lip_sync import append_mouth_cues
from api.services.assistant.alignment.lip_sync import read_mouth_cues

MAX_ALIGNMENT_BYTES=196608
MAX_INTERNAL_AUDIO_BYTES=4_300_000

def attach_alignment(audio, alignment):
    payload=json.dumps(alignment,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')
    if len(payload)>MAX_ALIGNMENT_BYTES:raise ValueError('Alignment too large')
    result=audio+b'isap'+struct.pack('<I',len(payload))+payload+b'\0'*(len(payload)%2)
    return result[:4]+struct.pack('<I',len(result)-8)+result[8:]

def detach_alignment(audio):
    if len(audio)>MAX_INTERNAL_AUDIO_BYTES or audio[:4]!=b'RIFF' or audio[8:12]!=b'WAVE' or int.from_bytes(audio[4:8],'little')!=len(audio)-8:
        raise ValueError('Invalid private WAV')
    offset=12;parts=[audio[:12]];alignment=None
    while offset+8<=len(audio):
        size=int.from_bytes(audio[offset+4:offset+8],'little');end=offset+8+size
        padded=end+size%2
        if padded>len(audio):raise ValueError('Truncated private WAV')
        if audio[offset:offset+4]==b'isap':
            if alignment is not None or size>MAX_ALIGNMENT_BYTES:raise ValueError('Invalid private alignment')
            alignment=json.loads(audio[offset+8:end])
        elif audio[offset:offset+4]!=b'isav':
            parts.append(audio[offset:padded])
        offset=padded
    if offset!=len(audio) or not isinstance(alignment,dict):raise ValueError('Missing private alignment')
    result=b''.join(parts)
    return result[:4]+struct.pack('<I',len(result)-8)+result[8:],alignment

def infer(audio, language):
    import base64
    import hashlib
    import numpy as np
    from api.services.assistant.alignment.isa_ml.phoneme_identity import identity_features
    from api.services.assistant.alignment.isa_ml.forest_classifier import predict
    from api.services.assistant.alignment.isa_ml.classifier import timeline
    if language not in ('es','en'):raise ValueError('Invalid language')
    public,alignment=detach_alignment(audio)
    with wave.open(io.BytesIO(public)) as wav:
        rate=wav.getframerate();frames=wav.getnframes()
        if wav.getnchannels()!=1 or wav.getsampwidth()!=2 or rate!=22050 or not 0<frames<=rate*90:raise ValueError('Invalid audio')
        pcm=wav.readframes(frames)
    alignment['sha256_pcm']=hashlib.sha256(struct.pack('<I',rate)+pcm).hexdigest()
    folder=Path(__file__).with_name('isa_ml')/'weights'
    weights=(folder/f'{language}.npz').read_bytes()
    provenance=json.loads((folder/'provenance.json').read_text())
    if hashlib.sha256(weights).hexdigest()!=provenance['weights_sha256'][language]:raise ValueError('Changed RF weights')
    model=json.loads((folder/f'{language}.json').read_text())
    model['forest_npz']=base64.b64encode(weights).decode('ascii')
    samples=np.frombuffer(pcm,dtype='<i2').astype(float)/32768
    features,_,hop=identity_features(samples,rate,alignment,model['phoneme_vocabulary'])
    cues=read_mouth_cues({'mouthCues':timeline(predict(model,features),hop,frames/rate)},frames/rate)
    public=append_mouth_cues(public,cues)
    marker=b'{"engine":"isa-rf-v2"}'
    result=public+b'isam'+struct.pack('<I',len(marker))+marker+b'\0'*(len(marker)%2)
    return result[:4]+struct.pack('<I',len(result)-8)+result[8:]

def classify_after_synthesis(audio, language):
    result=subprocess.run([sys.executable,'-X','utf8','-m','api.services.assistant.alignment.own_lip_sync',language],
        input=audio,stdout=subprocess.PIPE,timeout=30,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),
        cwd=Path(__file__).resolve().parents[4])
    if result.returncode or not result.stdout:raise ValueError('RF inference failed')
    return result.stdout

if __name__=='__main__':
    try:
        data=sys.stdin.buffer.read(MAX_INTERNAL_AUDIO_BYTES+1)
        sys.stdout.buffer.write(infer(data,sys.argv[1]))
    except Exception:
        raise SystemExit(1)
