"""Real sequential Piper/RF release probe with per-process peak memory."""
import io
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

WRAPPER=r'''
import ctypes,ctypes.wintypes as w,json,runpy,sys
mode=sys.argv.pop(1)
try:
 if mode=='piper':
  script=sys.argv.pop(1);sys.argv[0]=script;runpy.run_path(script,run_name='__main__')
 else:runpy.run_module('api.services.assistant.alignment.own_lip_sync',run_name='__main__')
finally:
 if sys.platform=='win32':
  class Memory(ctypes.Structure):
   _fields_=[('cb',w.DWORD),('faults',w.DWORD)]+[(n,ctypes.c_size_t) for n in ('peak','rss','paged_peak','paged','nonpaged_peak','nonpaged','commit','commit_peak')]
  m=Memory();m.cb=ctypes.sizeof(m)
  k=ctypes.WinDLL('kernel32');k.GetCurrentProcess.restype=w.HANDLE
  p=ctypes.WinDLL('psapi');p.GetProcessMemoryInfo.argtypes=[w.HANDLE,ctypes.POINTER(Memory),w.DWORD]
  if p.GetProcessMemoryInfo(k.GetCurrentProcess(),ctypes.byref(m),m.cb):print(json.dumps({'release_peak_mib':round(m.peak/1048576,2)}),file=sys.stderr)
'''

def run(mode,args,payload):
 start=time.perf_counter()
 result=subprocess.run([sys.executable,'-X','utf8','-c',WRAPPER,mode,*args],input=payload,
   stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=ROOT,timeout=75)
 if result.returncode:raise RuntimeError('Release probe failed: '+result.stderr.decode(errors='replace')[-500:])
 peak=[json.loads(line) for line in result.stderr.decode(errors='replace').splitlines() if line.startswith('{"release_peak_mib"')]
 return result.stdout,{'seconds':round(time.perf_counter()-start,3),**(peak[-1] if peak else {})}

def main():
 import os
 os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
 import django;django.setup()
 from django.conf import settings
 from api.services.assistant.direction.isa_local_director import direct_locally
 sys.path.insert(0,str(ROOT/'experiments/isa_classifier'))
 from narration import app_performance
 from classifier import read_recording
 out=ROOT/'tmp/isa-own-production-probe';out.mkdir(exist_ok=True)
 samples={'es':['Puede llover esta tarde. Llevá una campera liviana.',
   'Antes de salir a caminar, revisá el viento y las nubes. Llevá agua y una campera liviana. Si empieza a llover, buscá un lugar cubierto y esperá con calma.'],
   'en':['It may rain this afternoon. Bring a light jacket.',
   'Before going for a walk, check the wind and clouds. Bring water and a light jacket. If rain starts, find a covered place and wait calmly.']}
 report=[]
 for language,texts in samples.items():
  for i,text in enumerate(texts):
   spoken,segments=app_performance(text,language,direct_locally)
   payload=json.dumps({'texto':spoken,'segmentos':segments},ensure_ascii=False).encode()
   private,piper=run('piper',[str(ROOT/'api/services/assistant/voice/voice_worker.py'),str(settings.ISA_MODEL_DIR),language,'--performance','--own-lip-sync'],payload)
   public,rf=run('rf',[language],private)
   file=out/f'{language}-{i}.wav';file.write_bytes(public)
   _,_,cues,_=read_recording(file)
   assert cues and b'isap' not in public and b'isa-rf-v2' in public
   report.append({'language':language,'case':i,'piper':piper,'rf':rf,'cues':len(cues),'file':file.name})
 (out/'release-profile.json').write_text(json.dumps(report,indent=2),encoding='utf8')
 print(json.dumps(report))

if __name__=='__main__':main()
