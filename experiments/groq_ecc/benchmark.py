"""Bounded same-model A/B, API usage and isolated response-cache experiment."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
import django
django.setup()
from django.conf import settings
import httpx
from groq import Groq, APIError
from api.services.assistant.recommendations import build_messages
from api.services.assistant.recommendations import _completion_text
from api.services.assistant.recommendations import GROQ_BASE_URL
from api.tests.assistant.test_recommendations import weather_snapshot

OUT=ROOT/'tmp/groq-ecc-benchmark-v1'
SCENARIOS=[('cold',3,0,65,'cielo claro'),('hot',33,12,40,'cielo claro'),
           ('rain',15,18,90,'lluvia ligera'),('wind',18,42,55,'nublado')]

def cases():
    output=[]
    for name,temp,wind,humidity,description in SCENARIOS:
        for language in ('es','en'):
            snap=deepcopy(weather_snapshot())
            snap.actual.update(temperatura_c=temp,sensacion_c=temp-2,humedad_pct=humidity,
                               viento_kmh=wind,descripcion=description,fecha_utc='2026-11-17T12:00:00Z')
            for i,row in enumerate(snap.pronostico['intervalos']):
                row.update(temperatura_c=temp-2+i,descripcion=description,
                    fecha_utc=(datetime(2026,11,17,15,tzinfo=timezone.utc)+timedelta(hours=i*3)).isoformat().replace('+00:00','Z'))
            output.append((name,language,snap))
    return output

def summarize(rows):
    result={}
    for arm in ('groq','local'):
        subset=[r for r in rows if r['phase']=='paired' and r['arm']==arm]
        if not subset:continue
        result[arm]={'requests':len(subset),'valid':sum(r['valid'] for r in subset),
            'finish_reasons':dict(Counter(r['finish_reason'] for r in subset)),
            'prompt_tokens':sum(r['prompt_tokens'] for r in subset),
            'completion_tokens':sum(r['completion_tokens'] for r in subset),
            'cached_prompt_tokens':sum(r['cached_prompt_tokens'] for r in subset),
            'median_wall_seconds':statistics.median(r['wall_seconds'] for r in subset)}
    return result

def main():
    if not settings.GROQ_API_KEY.strip():raise RuntimeError('Groq key is not configured')
    OUT.mkdir(parents=True,exist_ok=True)
    previous=None
    if (OUT/'results.json').exists():
        if '--resume' not in sys.argv:raise RuntimeError('Existing benchmark: use --resume after an interrupted run')
        previous=json.loads((OUT/'results.json').read_text(encoding='utf8'))
        if previous['status']!='provider_failure':raise RuntimeError('Only an interrupted benchmark may resume')
    model=settings.GROQ_MODEL.strip()
    if previous and previous['model']!=model:raise RuntimeError('Model changed during experiment')
    rows=previous['rows'] if previous else []
    requests=previous['real_requests'] if previous else 0
    tokens=previous['observed_total_tokens'] if previous else 0
    reserve=max(settings.GROQ_MAX_COMPLETION_TOKENS,512)
    reasoning={}
    if model in ('openai/gpt-oss-20b','openai/gpt-oss-120b'):
        reserve=max(reserve,1024);reasoning={'reasoning_effort':'low','include_reasoning':False}
    start=time.perf_counter()
    def persist(**extra):
        result={'model':model,'completion_cap':reserve,'same_model':True,'ecc_installed':False,
            'real_requests':requests,'observed_total_tokens':tokens,'rows':rows,
            'summary':summarize(rows),**extra}
        (OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
        return result
    timeout=httpx.Timeout(connect=5,read=25,write=5,pool=5)
    try:
        with httpx.Client(timeout=timeout,follow_redirects=False,trust_env=False) as http:
            with Groq(api_key=settings.GROQ_API_KEY,base_url=GROQ_BASE_URL,
                      http_client=http,timeout=timeout,max_retries=0) as client:
                def call(case,arm,phase):
                    nonlocal requests,tokens
                    name,language,snap=case
                    existing=next((r for r in rows if (r['scenario'],r['language'],r['arm'],r['phase'])==(name,language,arm,phase)),None)
                    if existing:return existing
                    if requests>=23 or tokens>45000:raise RuntimeError('Experiment budget reached')
                    if requests:time.sleep(22)
                    messages=build_messages(snap,language=language,director=arm)
                    before=time.perf_counter();requests+=1
                    response=client.chat.completions.create(model=model,messages=messages,
                        max_completion_tokens=reserve,n=1,stream=False,tool_choice='none',
                        response_format={'type':'json_object'},**reasoning)
                    elapsed=time.perf_counter()-before
                    usage=response.usage.model_dump() if response.usage else {}
                    parsed=_completion_text(response,director=arm,language=language)
                    cached=(usage.get('prompt_tokens_details') or {}).get('cached_tokens') or 0
                    tokens+=usage.get('total_tokens',0)
                    row={'scenario':name,'language':language,'arm':arm,'phase':phase,
                        'valid':parsed is not None,'wall_seconds':round(elapsed,4),
                        'prompt_tokens':usage.get('prompt_tokens',0),
                        'completion_tokens':usage.get('completion_tokens',0),
                        'cached_prompt_tokens':cached,'usage':usage,
                        'input_characters':sum(len(m['content']) for m in messages),
                        'finish_reason':response.choices[0].finish_reason,
                        'advice':parsed,'raw_response_chars':len(response.choices[0].message.content or '')}
                    rows.append(row);persist(status='running')
                    print(json.dumps({k:row[k] for k in ('scenario','language','arm','phase','valid','prompt_tokens','completion_tokens','cached_prompt_tokens','wall_seconds')}),flush=True)
                    return row
                workload=cases();rng=random.Random(20261117)
                for case in workload:
                    arms=['groq','local'];rng.shuffle(arms)
                    for arm in arms:call(case,arm,'paired')
                for case in workload[:4]:call(case,'groq','prefix-repeat')
                cache={};hits=0
                for case in [workload[0],workload[1],workload[0],workload[1]]:
                    messages=build_messages(case[2],language=case[1],director='groq')
                    key=hashlib.sha256(json.dumps([model,reserve,reasoning,messages],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                    cached=cache.get(key)
                    if cached and time.monotonic()-cached[0]<300:
                        hits+=1;continue
                    row=call(case,'groq','response-cache');cache[key]=(time.monotonic(),row)
                result=persist(status='complete',cache_test={'logical_requests':4,'real_requests':len(cache),
                    'hits':hits,'ttl_seconds':300,'synthetic_repetitive_workload':True},
                    elapsed_seconds=round(time.perf_counter()-start,2))
                print(json.dumps({'status':'complete','summary':result['summary'],'cache_test':result['cache_test']}))
    except (APIError,httpx.HTTPError) as exc:
        persist(status='provider_failure',error_type=type(exc).__name__,http_status=getattr(exc,'status_code',None))
        print(json.dumps({'status':'provider_failure','error_type':type(exc).__name__,'http_status':getattr(exc,'status_code',None)}))
        raise SystemExit(1)

if __name__=='__main__':main()
