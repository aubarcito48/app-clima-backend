"""Controlled local experiment: one fixed advice, two real direction plans.

At most one Groq request per uncached run; no retries, env edits or deployment.
Only the invented public sample text is sent. Never print keys/provider errors.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time
import wave

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
TEXT='Usá una campera liviana por el viento. Más tarde puede llover; evitá el calzado abierto y llevá un paraguas.'


def wav_info(audio):
    with wave.open(io.BytesIO(audio)) as wav:
        duration=wav.getnframes()/wav.getframerate()
    offset=12;timeline=None
    while offset+8<=len(audio):
        size=int.from_bytes(audio[offset+4:offset+8],'little')
        if offset+8+size>len(audio):raise ValueError('Invalid RIFF chunk')
        if audio[offset:offset+4]==b'isac':timeline=json.loads(audio[offset+8:offset+8+size])
        offset+=8+size+size%2
    if not timeline or abs(timeline[-1]['until']-duration)>.001:raise ValueError('Missing real Piper timeline')
    return {'duration':duration,'timeline':timeline,'sha256':hashlib.sha256(audio).hexdigest()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'tmp/isa-directors-6')
    args=parser.parse_args();folder=args.output.resolve()
    if not folder.is_relative_to((ROOT/'tmp').resolve()):parser.error('Output must remain under backend tmp')
    folder.mkdir(parents=True,exist_ok=True)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
    import django
    django.setup()
    from django.conf import settings
    from django.test import override_settings
    from api.services.isa_local_director import direct_locally
    from api.services.isa_performance import read_segments
    from api.services.recommendations import SYSTEM_PROMPT,_completion_text,GROQ_BASE_URL
    from api.services.voice import synthesize
    from groq import Groq
    import httpx

    plan_path=folder/'plans.json'
    if plan_path.exists():
        report=json.loads(plan_path.read_text(encoding='utf8'))
        if report['text']!=TEXT:raise ValueError('Cached advice differs')
        print('Reusing the previously saved Groq plan; no API request.',flush=True)
    else:
        local=direct_locally(TEXT,language='es')
        model=settings.GROQ_MODEL
        system=SYSTEM_PROMPT+'\nEl consejo ya está aprobado. No lo reescribas ni interpretes clima nuevo. Copiá exactamente el texto recibido en texto y dirigí únicamente su actuación con segmentos válidos. No agregues palabras.'
        started=time.perf_counter()
        timeout=httpx.Timeout(connect=8,read=35,write=8,pool=8)
        with httpx.Client(timeout=timeout,trust_env=False,follow_redirects=False) as http_client:
            with Groq(api_key=settings.GROQ_API_KEY,base_url=GROQ_BASE_URL,http_client=http_client,max_retries=0) as client:
                options={'reasoning_effort':'low','include_reasoning':False} if model in {'openai/gpt-oss-20b','openai/gpt-oss-120b'} else {}
                response=client.chat.completions.create(model=model,messages=[{'role':'system','content':system},{'role':'user','content':json.dumps({'texto_aprobado':TEXT},ensure_ascii=False)}],
                    max_completion_tokens=1024,n=1,stream=False,tool_choice='none',response_format={'type':'json_object'},**options)
        usage=response.usage.model_dump() if response.usage else None
        result=_completion_text(response,director='groq',language='es')
        if not result or result['texto']!=TEXT or not result.get('segmentos'):
            (folder/'failed-usage.json').write_text(json.dumps({'usage':usage,'status':'invalid_fixed_text_plan'},indent=2),encoding='utf8')
            raise ValueError('Groq did not return the same text and a valid plan; no automatic retry')
        report={'experiment':6,'reviewed':False,'text':TEXT,'local':local,'groq':result['segmentos'],
                'model':model,'usage':usage,'groqRequestSeconds':round(time.perf_counter()-started,3),
                'requestCount':1,'scope':'Fixed-text direction only, not the total production advice request.'}
        plan_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps({'groq_plan_saved':True,'model':model,'usage':usage},ensure_ascii=False),flush=True)
    for mode in ('local','groq'):
        plan=read_segments(report[mode],TEXT)
        target=folder/f'{mode}.wav'
        if target.exists() and mode in report.get('audio',{}) and hashlib.sha256(target.read_bytes()).hexdigest()==report['audio'][mode]['sha256']:
            continue
        started=time.perf_counter()
        with override_settings(ISA_LIP_SYNC='off'):
            audio=synthesize(TEXT,language='es',segments=plan)
        info=wav_info(audio);info['synthesisSeconds']=round(time.perf_counter()-started,3)
        target.write_bytes(audio);report.setdefault('audio',{})[mode]=info
        print(json.dumps({'piper':mode,'duration':round(info['duration'],3),'seconds':info['synthesisSeconds']}),flush=True)
        plan_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    report['voiceModel']='es_ES-sharvard-medium.onnx; female speaker 1'
    report['lipSync']='off in this experiment process only; no Rhubarb-dependent switches'
    plan_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(f'Ready: {plan_path}',flush=True)


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'experiment':6,'status':'incomplete','errorType':type(error).__name__,
                          'note':'No raw provider error, key or environment values printed; no automatic retries.'}),flush=True)
        raise SystemExit(1)
