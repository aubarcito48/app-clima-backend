"""Make a standalone audio/cue inspection page, not a replacement Isa renderer."""

import argparse
import base64
import io
import json
from pathlib import Path
import sys
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.services.lip_sync import read_mouth_cues


def build_preview(audio):
    with wave.open(io.BytesIO(audio)) as wav:
        duration = wav.getnframes() / wav.getframerate()
    offset, data = 12, None
    while offset + 8 <= len(audio):
        size = int.from_bytes(audio[offset + 4:offset + 8], 'little')
        if offset + 8 + size > len(audio):
            raise ValueError('Invalid RIFF chunk')
        if audio[offset:offset + 4] == b'isav':
            data = json.loads(audio[offset + 8:offset + 8 + size])
        offset += 8 + size + size % 2
    cues = read_mouth_cues({'mouthCues': data}, duration)
    return TEMPLATE.replace('__AUDIO__', base64.b64encode(audio).decode('ascii')).replace(
        '__CUES__', json.dumps(cues, separators=(',', ':')))


TEMPLATE = '''<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Isa · diagnóstico de boca</title><style>
body{font:17px/1.6 system-ui;background:#eef8fc;color:#17364c;margin:0;padding:clamp(20px,5vw,60px)}
main{max-width:850px;margin:auto}h1{line-height:1.2}audio{width:100%;margin:20px 0}
#current{background:white;border:1px solid #bad4e2;border-radius:18px;padding:25px;display:flex;gap:25px;align-items:center}
#shape{font:bold 68px/1 system-ui;color:#126d91}#description{font-size:20px}#time{font-variant-numeric:tabular-nums}
#timeline{display:flex;height:55px;margin:25px 0;border:1px solid #8baabb;overflow:hidden;border-radius:9px}
button{min-width:1px;padding:0;border:0;border-right:1px solid white;cursor:pointer;color:#17364c}
button:focus-visible{outline:3px solid black;outline-offset:-3px}.active{box-shadow:inset 0 0 0 3px #102d40}
li{margin:8px 0}small{display:block}.note{color:#496579}
</style><main><h1>Isa: audio y formas de boca</h1>
<p>Esta es una vista de diagnóstico. Las letras representan formas propuestas por Rhubarb;
no es una animación nueva de Isa ni una medición de precisión.</p>
<audio id="audio" controls preload="metadata" src="data:audio/wav;base64,__AUDIO__"></audio>
<section id="current" aria-label="Forma actual"><span id="shape">X</span>
<div><div id="description">Reposo</div><small id="time">0,00 s</small></div></section>
<div id="timeline" aria-label="Marcas de boca; activar para escuchar desde ese momento"></div>
<p class="note">Escuchá dónde cierran los labios en m/p/b, los silencios y los cambios de forma.
Una letra indica una forma de boca, no una transcripción exacta del sonido.</p>
<details><summary>Formas para revisar con las imágenes</summary><ul id="catalogue"></ul></details>
<p><a href="https://github.com/DanielSWolf/rhubarb-lip-sync#mouth-shapes">Catálogo oficial de Rhubarb</a></p>
</main><script>
const cues=__CUES__;
const descriptions={A:'Labios juntos con leve presión (m/p/b)',B:'Boca apenas abierta, dientes cercanos',
C:'Boca abierta media',D:'Boca bien abierta',E:'Boca algo redondeada',F:'Labios fruncidos y redondeados',
G:'Dientes superiores sobre el labio inferior',H:'Lengua elevada detrás de los dientes superiores',X:'Reposo con labios relajados'};
const colors={A:'#a9d6e5',B:'#caf0f8',C:'#c2e5d1',D:'#f9d99a',E:'#f3c5cf',F:'#d1c3ed',G:'#bdd9b5',H:'#e1d0bf',X:'#e3e9ed'};
const audio=document.getElementById('audio'), timeline=document.getElementById('timeline');
const buttons=cues.map(cue=>{const b=document.createElement('button');b.style.flex=String(cue.end-cue.start);
b.style.background=colors[cue.value];b.textContent=cue.end-cue.start>.14?cue.value:'';
b.title=`${cue.start.toFixed(2)}–${cue.end.toFixed(2)} s · ${descriptions[cue.value]}`;
b.setAttribute('aria-label',b.title);b.onclick=()=>{audio.currentTime=cue.start;update()};timeline.append(b);return b});
for(const [key,value] of Object.entries(descriptions)){const li=document.createElement('li');li.textContent=key+' · '+value;document.getElementById('catalogue').append(li)}
let previous=-1;
function update(){const t=audio.currentTime;const index=cues.findIndex(c=>t>=c.start&&t<c.end);
if(index!==previous){buttons[previous]?.classList.remove('active');buttons[index]?.classList.add('active');previous=index}
const shape=index<0?'X':cues[index].value;document.getElementById('shape').textContent=shape;
document.getElementById('description').textContent=descriptions[shape];document.getElementById('time').textContent=t.toFixed(2)+' s';}
function animate(){update();if(!audio.paused)requestAnimationFrame(animate)}
audio.addEventListener('play',animate);audio.addEventListener('seeked',update);audio.addEventListener('ended',update);
update();
</script></html>'''


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wav', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = args.output or args.wav.with_suffix('.html')
    output.write_text(build_preview(args.wav.read_bytes()), encoding='utf8')
    print(output)
