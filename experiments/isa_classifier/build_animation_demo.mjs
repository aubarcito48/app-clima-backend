import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const frontend = path.resolve(process.argv[2]);
const folder = path.resolve(process.argv[3]);
const { build } = await import(pathToFileURL(path.join(frontend, 'node_modules/esbuild/lib/main.js')));
const data = JSON.parse(await readFile(path.join(folder, 'demo.json'), 'utf8'));
const labels = { v3: 'V3 · referencia propia', v4: 'V4 · ensayo de balanceo', v5: 'V5 · entrenamiento anterior', v6: 'V6 · consejos breves y saludo', v7: 'V7 · más audios y señales temporales' };
labels.v8 = 'Fonemas Piper · experimental';
labels.v9 = 'Híbrido fonético entrenado';
const modelOptions = Object.keys(data.cases[0].versions).map(version => {
  if (!labels[version]) throw Error('Unknown demo model version');
  return `<option value="${version}">${labels[version]}</option>`;
}).join('');
const entry = `
import {createIsaPortrait} from './src/app/shared/isabel/isa-portrait.ts';
import {createIsaPlayback} from './src/app/shared/isabel/isa-playback.ts';
const data=${JSON.stringify(data).replaceAll('<', '\\u003c')};
const $=id=>document.getElementById(id),audio=$('audio');
let controllers=[],reference,own,sample,ready=false,raf,token=0;
const buffer=src=>Uint8Array.from(atob(src.split(',')[1]),c=>c.charCodeAt(0)).buffer;
function stopClock(){if(raf!==undefined)cancelAnimationFrame(raf);raf=undefined}
function update(){if(!ready)return;const t=Math.min(sample.duration,audio.currentTime);
 const times=[reference.sourceSecondsAt(t),own.sourceSecondsAt(t)];
 controllers.forEach((c,i)=>c.setSpeechTime(times[i]));
 ['reference','own'].forEach((id,i)=>$(id).dataset.sourceTime=times[i]);
 const a=sample.reference.find(c=>c.start<=t&&t<c.end)?.value??'X';
 const b=sample.versions[$('model').value].cues.find(c=>c.start<=t&&t<c.end)?.value??'X';
 $('shapes').textContent='Marcas a '+t.toFixed(3)+' s: Rhubarb '+a+' · propio '+b;
 $('seek').value=t;$('time').textContent=t.toFixed(3)+' / '+sample.duration.toFixed(3)+' s';
}
function tick(){update();if(!audio.paused&&!audio.ended)raf=requestAnimationFrame(tick)}
async function change(){const generation=++token;ready=false;stopClock();audio.pause();$('play').disabled=true;
 sample=data.cases.find(c=>c.language===$('language').value);$('text').textContent=sample.text;
 $('policy').textContent=sample.language==='es'&&sample.duration>=7.5
 ? 'El selector español conserva vueltas completas del video: puede mostrar pocos cambios entre motores durante esas vueltas. Revisá también las marcas y el tramo final; similitud visual no implica igual precisión acústica.'
 : 'Ambos motores usan el mismo selector de frames para aislar el cambio de marcas acústicas.';
 reference=createIsaPlayback(buffer(sample.audio),sample.language);
 own=createIsaPlayback(buffer(sample.versions[$('model').value].audio),sample.language);
 if(!reference||!own)throw Error('No se pudieron leer los tiempos de audio');
 let different=0,total=0;for(let t=0;t<sample.duration;t+=1/24){
  if(Math.floor(reference.sourceSecondsAt(t)*24)!==Math.floor(own.sourceSecondsAt(t)*24))different++;total++}
 $('comparison').textContent=different===0
 ? 'En esta muestra ambos motores producen el mismo plan de frames. No permite juzgar visualmente sus diferencias acústicas: mirá las marcas y las métricas del consejo.'
 : 'Los planes difieren en '+different+' de '+total+' instantes muestreados. Es diferencia de frames, no precisión.';
 controllers.forEach(c=>{c.setSpeaking(false);c.setSpeechLanguage(sample.language);c.setWorking(true)});
 const loaded=new Promise((resolve,reject)=>{audio.addEventListener('loadedmetadata',resolve,{once:true});audio.addEventListener('error',()=>reject(Error('No se pudo cargar el WAV')),{once:true})});
 audio.src=sample.audio;audio.load();await loaded;if(token!==generation)return;
 $('seek').max=sample.duration;ready=true;$('play').disabled=false;
 $('status').textContent='Listo. Un solo audio para ambas animaciones; banco de frames idéntico.';update();
}
audio.addEventListener('play',()=>{controllers.forEach(c=>{c.setWorking(false);c.setSpeaking(true)});stopClock();tick();$('status').textContent='Reproduciendo la comparación.'});
audio.addEventListener('pause',()=>{stopClock();update()});
audio.addEventListener('seeked',update);audio.addEventListener('timeupdate',update);
audio.addEventListener('ended',()=>{stopClock();controllers.forEach(c=>c.setSpeaking(false));$('status').textContent='Lectura terminada.'});
$('play').onclick=async()=>{audio.currentTime=0;try{await audio.play()}catch(error){$('status').textContent=error.message}};
$('seek').oninput=()=>{if(!ready)return;audio.pause();audio.currentTime=Number($('seek').value);controllers.forEach(c=>{c.setWorking(false);c.setSpeaking(true)});update()};
$('language').onchange=$('model').onchange=()=>change().catch(error=>$('status').textContent=error.message);
$('speed').onchange=()=>{audio.playbackRate=Number($('speed').value)};
$('theme').onclick=()=>{document.documentElement.dataset.theme=document.documentElement.dataset.theme==='dark'?'light':'dark'};
window.addEventListener('pagehide',()=>{audio.pause();stopClock();controllers.forEach(c=>c.destroy())},{once:true});
async function init(){try{for(const id of ['reference','own']){const c=await createIsaPortrait($(id));c.play('isa-awake');controllers.push(c)}await change()}catch(error){$('status').textContent=error.message}}
init();
`;
const bundled = await build({ stdin: { contents: entry, resolveDir: frontend, loader: 'js' },
  bundle: true, write: false, platform: 'browser', format: 'iife', target: 'es2022',
  plugins: [{ name: 'local-atlases', setup(b) {
    b.onLoad({ filter: /isa-(portrait|speech)-manifest(?:-en)?\.json$/ }, async ({ path: file }) => {
      const manifest = JSON.parse(await readFile(file, 'utf8'));
      const image = async name => 'data:image/webp;base64,' + (await readFile(path.join(frontend, 'public', name))).toString('base64');
      if (manifest.image) manifest.image = await image(manifest.image);
      for (const page of manifest.pages ?? []) page.image = await image(page.image);
      return { contents: JSON.stringify(manifest), loader: 'json' };
    });
  } }] });
const html = `<!doctype html><html lang="es" data-theme="light"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Isa · prueba del clasificador propio</title>
<style>body{font:16px system-ui;color:#123952;background:#edf8fc;margin:24px}main{max-width:1000px;margin:auto}
h1{font-size:1.8rem}button,select,input{font:inherit;border-radius:8px}button,select{padding:10px;border:1px solid #8bb6ca;background:#d9f2fa;color:#123952;max-width:100%}.controls label{min-width:0;max-width:100%}.controls select{max-width:100%;box-sizing:border-box}
.controls{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:16px 0}.pair{display:grid;grid-template-columns:1fr 1fr;gap:20px}
article{border:1px solid #8bb6ca;border-radius:16px;padding:16px;text-align:center}.portrait{height:320px;max-width:320px;margin:auto}
audio{width:100%}#seek{width:100%}blockquote{white-space:pre-line;margin:16px 0;border-left:3px solid #3297b5;padding:12px}
[data-theme=dark] body{background:#102838;color:#dff4ff}[data-theme=dark] article{background:#173d51}
@media(max-width:600px){body{margin:12px}.pair{grid-template-columns:1fr}.portrait{height:280px}}
</style><main><h1>Isa · voz y animación juntas</h1>
<p>Ensayo local. Izquierda: marcas Rhubarb. Derecha: ${data.cases[0].versions.v8 ? 'fonemas y duraciones de Piper, o clasificador V7 a elección' : 'predicción de nuestro clasificador'}, con el mismo audio y selector de frames.</p>
<div class="controls"><label>Idioma <select id="language"><option value="en">Inglés · Cori</option><option value="es">Español · Sharvard</option></select></label>
<label>Modelo propio <select id="model">${modelOptions}</select></label>
<button id="theme">Cambiar tema</button></div><blockquote id="text"></blockquote>
<div class="pair"><article><h2>Rhubarb</h2><div class="portrait" id="reference"></div></article>
<article><h2>${data.cases[0].versions.v8 ? 'Fonética / V7' : 'Clasificador propio'}</h2><div class="portrait" id="own"></div></article></div>
<div class="controls"><button id="play" disabled>Reproducir desde el inicio</button><label>Velocidad <select id="speed"><option value="1">Normal</option><option value="0.75">0,75× para revisar</option></select></label></div>
<audio id="audio" controls preload="metadata"></audio><label>Buscar instante <input id="seek" type="range" min="0" step="0.01" value="0"></label>
<p id="time"></p><p id="shapes"></p><p id="policy"></p><p id="comparison"></p><p id="status" role="status">Preparando las animaciones…</p>
<p>Los frames son completos: conservan rostro, ojos y cuerpo. Esta prueba aísla el cambio de marcas acústicas;
los frames candidatos de otras tomas están aparte en <a href="extra-frames.html">la selección visual</a>.
No es una medición de precisión ni una versión publicada.</p></main><script>${bundled.outputFiles[0].text.replaceAll('</script', '<\\/script')}</script></html>`;
await mkdir(folder, { recursive: true });
await writeFile(path.join(folder, 'index.html'), html);
const analysisBundle = await build({ stdin: { contents:
  "export {createIsaPlayback} from './src/app/shared/isabel/isa-playback.ts';",
  resolveDir: frontend, loader: 'js' }, bundle: true, write: false, format: 'esm', platform: 'node' });
const runtime = await import('data:text/javascript;base64,' + Buffer.from(analysisBundle.outputFiles[0].text).toString('base64'));
const decode = src => Uint8Array.from(Buffer.from(src.split(',')[1], 'base64')).buffer;
const diagnostics = data.cases.map(sample => {
  const reference = runtime.createIsaPlayback(decode(sample.audio), sample.language);
  const versions = Object.fromEntries(Object.entries(sample.versions).map(([name, version]) => {
    const own = runtime.createIsaPlayback(decode(version.audio), sample.language);
    if (!own || !reference) throw Error('Invalid playback timeline');
    let different = 0, count = 0;
    for (let t = 0; t < sample.duration; t += 1 / 24) {
      if (Math.floor(reference.sourceSecondsAt(t) * 24) !== Math.floor(own.sourceSecondsAt(t) * 24)) different++;
      count++;
    }
    return [name, { different_frame_instants: different, sampled_instants: count }];
  }));
  return { language: sample.language, sha256_pcm: sample.sha256_pcm, versions };
});
await writeFile(path.join(folder, 'demo-diagnostics.json'), JSON.stringify(diagnostics, null, 2));
console.log(path.join(folder, 'index.html'));
console.log(JSON.stringify(diagnostics));
