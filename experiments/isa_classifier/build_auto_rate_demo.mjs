import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { execFileSync } from 'node:child_process';
const frontend = path.resolve(process.argv[2]), folder = path.resolve(process.argv[3]);
const source = path.dirname(fileURLToPath(import.meta.url));
const { build } = await import(pathToFileURL(path.join(frontend, 'node_modules/esbuild/lib/main.js')));
const data = JSON.parse(await readFile(path.join(folder, 'comparison.json'), 'utf8'));
data.catalogs = {};
for (const language of ['es', 'en']) data.catalogs[language] = data.reviewedCatalogs?.[language] ?? JSON.parse(await readFile(path.join(frontend,
  `src/app/shared/isabel/isa-speech-selection${language === 'en' ? '-en' : ''}.json`), 'utf8'));
data.ranges = JSON.parse(await readFile(path.join(frontend, 'src/app/shared/isabel/isa-speech-ranges.json'), 'utf8'));
const result = await build({ entryPoints: [path.join(source, 'auto_rate_entry.mjs')], bundle: true, write: false,
  format: 'iife', target: 'es2022', plugins: [{ name: 'offline', setup(b) {
    b.onResolve({ filter: /^isa\/portrait$/ }, () => data.functionalityReview
      ? { path: 'router', namespace: 'portrait-router' }
      : { path: path.join(frontend, 'src/app/shared/isabel/isa-portrait.ts') });
    b.onLoad({filter:/.*/,namespace:'portrait-router'},()=>({contents:
      `import {createIsaPortrait as before} from 'isa/portrait-before';
       import {createIsaPortrait as after} from 'isa/portrait-after';
       export const createIsaPortrait=host=>(host.id==='baseline'?before:after)(host);`,loader:'js'}));
    b.onResolve({filter:/^isa\/portrait-(before|after)$/},args=>({path:args.path.endsWith('before')?'before':'after',namespace:'portrait-version'}));
    b.onLoad({filter:/.*/,namespace:'portrait-version'},async args=>{
      const file=path.join(frontend,'src/app/shared/isabel/isa-portrait.ts');
      let text=args.path==='before'
        ? execFileSync('git',['show',data.functionalityReview.baselineCommit+':src/app/shared/isabel/isa-portrait.ts'],{cwd:frontend,encoding:'utf8'})
        : await readFile(file,'utf8');
      if(args.path==='before')text=text.replace("'./isa-speech-manifest.json'","'isa/legacy-manifest/es'")
        .replace("'./isa-speech-manifest-en.json'","'isa/legacy-manifest/en'");
      return {contents:portraitOverlay(text),loader:'ts',resolveDir:path.dirname(file)};
    });
    b.onResolve({filter:/^isa\/legacy-manifest\//},args=>({path:args.path.endsWith('/es')?'es':'en',namespace:'legacy-manifest'}));
    b.onLoad({filter:/.*/,namespace:'legacy-manifest'},async args=>{
      const file='src/app/shared/isabel/isa-speech-manifest'+(args.path==='en'?'-en':'')+'.json';
      const manifest=JSON.parse(execFileSync('git',['show',data.functionalityReview.baselineCommit+':'+file],{cwd:frontend,encoding:'utf8'}));
      for(const page of manifest.pages)page.image='data:image/webp;base64,'+(await readFile(path.join(frontend,'public',page.image))).toString('base64');
      return {contents:JSON.stringify(manifest),loader:'json'};
    });
    b.onResolve({ filter: /^isa\/timing-data$/ }, () => ({ path: 'data', namespace: 'timing' }));
    b.onLoad({ filter: /.*/, namespace: 'timing' }, () => ({ contents: JSON.stringify(data), loader: 'json' }));
    function portraitOverlay(text) {
      text = text.replace("import ranges from './isa-speech-ranges.json';", "import baseRanges from './isa-speech-ranges.json';");
      const marker = 'export async function createIsaPortrait(host: HTMLElement) {';
      if (!text.includes(marker) || !text.includes('import baseRanges')) throw Error('Portrait overlay source changed');
      text = text.replace(marker, marker + '\nconst ranges = host.dataset.visualPolicy === "automatic" ? '
        + JSON.stringify(data.visualPolicies.automatic.ranges) + ' : baseRanges;');
      const tileMarker = 'const index = Math.floor(speechPosition) % speechAtlas.sourceFrames.length;';
      if (!text.includes(tileMarker)) throw Error('Portrait frame observation source changed');
      text = text.replace(tileMarker, tileMarker + '\ncanvas.dataset.atlasFrame = String(index);');
      const methodMarker = 'setSpeechTime(seconds: number) {';
      if (!text.includes(methodMarker)) throw Error('Portrait range hook source changed');
      text = text.replace(methodMarker, `setExperimentalSpeechRange(first: number, end: number) {
        if (!Number.isInteger(first) || !Number.isInteger(end) || first < 0 || end <= first || end > speechAtlas.sourceFrames.length) throw Error('Invalid experimental range');
        SPEECH_START = first; SPEECH_END = end; speechPosition = first;
        canvas.dataset.rangeFirst = String(first); canvas.dataset.rangeEnd = String(end);
      },\n` + methodMarker);
      return text;
    }
    if (data.visualPolicies) b.onLoad({ filter: /isa-portrait\.ts$/ }, async ({ path: file }) =>
      ({ contents: portraitOverlay(await readFile(file, 'utf8')), loader: 'ts' }));
    b.onLoad({ filter: /isa-(portrait|speech)-manifest(?:-en)?\.json$/ }, async ({ path: file }) => {
      const manifest = JSON.parse(await readFile(file, 'utf8'));
      const image = async name => 'data:image/webp;base64,' + (await readFile(path.join(frontend, 'public', name))).toString('base64');
      if (manifest.image) manifest.image = await image(manifest.image);
      for (const page of manifest.pages ?? []) page.image = await image(page.image);
      return { contents: JSON.stringify(manifest), loader: 'json' };
    });
  } }] });
const card = (name, title) => `<article><h2>${title}</h2><div class="portrait" id="${name}"></div><button id="${name}Play" disabled>Escuchar ${name === 'baseline' ? 'actual' : 'automático'}</button><audio id="${name}Audio" controls preload="metadata"></audio><label>Instante del audio<input id="${name}Seek" type="range" min="0" step="0.01" value="0"></label><p id="${name}Time"></p><p id="${name}Phone"></p><canvas id="${name}Bars" width="520" height="180" aria-label="Energía, pausas y formas de boca"></canvas></article>`;
let html = `<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Isa · velocidad automática</title>
<style>body{font:16px system-ui;background:#edf8fc;color:#123952;margin:24px}main{max-width:1100px;margin:auto}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}article{border:1px solid #8bb6ca;border-radius:8px;padding:16px;text-align:center}.portrait{height:320px;max-width:320px;margin:auto}button,select{font:inherit;border:1px solid #8bb6ca;border-radius:8px;padding:10px;color:inherit;background:white}audio{width:100%;display:block;margin-top:12px}blockquote{white-space:pre-line;margin:20px 0;border-left:3px solid #3297b5;padding:12px}table{width:100%;border-collapse:collapse}td,th{padding:12px;border-bottom:1px solid #b8dce9;text-align:left}.table{overflow-x:auto}button:focus-visible,select:focus-visible{outline:3px solid #2485a8}@media(max-width:650px){body{margin:12px}.pair{grid-template-columns:1fr}}</style>
<style>canvas{display:block;width:100%;height:180px;background:white;border-radius:8px}input[type=range]{display:block;width:100%}.controls{display:flex;flex-wrap:wrap;gap:16px;align-items:center;margin:16px 0}.controls label{min-width:0;max-width:100%}select{max-width:100%;box-sizing:border-box}</style>
<main><h1>Isa · voz y animación con ajuste automático</h1><p>Compará el ritmo actual con el ajuste por frase. El sistema mide la primera síntesis, reduce sólo las frases rápidas y regenera voz, fonemas y animación. Los objetivos de velocidad son experimentales.</p>
<div class="controls"><label>Muestra <select id="scenario"></select></label><label>Clasificación <select id="model"></select></label><label><input id="accelerate" type="checkbox">Acelerar automáticamente cierres largos de la animación (perfil inicial según idioma)</label></div>
<label>Voz <select id="language"><option value="en">Cori · inglés</option><option value="es">Sharvard · español</option></select></label><p id="evaluation"></p><blockquote id="text"></blockquote>
<div class="pair">${card('baseline', 'Ritmo actual')}${card('automatic', 'Velocidad automática')}</div><p id="status" role="status">Preparando…</p>
<p>Gris: energía · verde: pausas insertadas · amarillo: baja energía candidata · primera barra: boca solicitada · segunda: frame elegido · tercera: control del modelo anterior. Cada columna tiene su propio reloj. Las etiquetas visuales y acústicas siguen siendo provisionales.</p>
${data.verified_pauses ? '<p>Las pausas verdes se verificaron contra PCM cero y marcas de la misma síntesis, incluidos huecos entre chunks. Las etiquetas de entrenamiento se corrigen sólo en interiores completamente silenciosos; la boca predicha no se fuerza a X para calcular las puntuaciones.</p>' : ''}
<p>Escuchá una versión y después la otra; al iniciar una, la otra se detiene. La velocidad del reproductor es normal (1×): la diferencia está en la voz generada. Ambas usan el mismo banco y el mismo planificador temporal.</p>
<h2>Decisiones automáticas</h2><div class="table"><table><thead><tr><th>Frase</th><th>Decisión</th><th>Ritmo medido antes → después</th></tr></thead><tbody id="decisions"></tbody></table></div>
<p>No hay cambios en producción. ${data.models ? 'Los clasificadores fueron entrenados por separado; este visor no entrena mientras reproduce. El controlador de velocidad sigue siendo una regla experimental.' : 'No hubo nuevo entrenamiento en esta prueba.'} Se mantienen las pausas insertadas y los saludos. El ritmo medio de una frase no identifica por sí solo errores locales de sincronización.</p></main><script>${result.outputFiles[0].text.replaceAll('</script', '<\\/script')}</script></html>`;
if (data.compareModels) {
  const escapeHtml = text => text.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
  const beforeLabel = escapeHtml(data.models.previous), afterLabel = escapeHtml(data.models.balanced);
  html = html.replace('<h2>Ritmo actual</h2>', `<h2>${beforeLabel}</h2>`)
    .replace('<h2>Velocidad automática</h2>', `<h2>${afterLabel}</h2>`)
    .replace('Isa · voz y animación con ajuste automático', `Isa · ${afterLabel} frente a ${beforeLabel}`)
    .replace('<h2>Decisiones automáticas</h2>', '<h2 hidden>Decisiones automáticas</h2>')
    .replace('<div class="table">', '<div class="table" hidden>')
    .replace('Cada columna tiene su propio reloj.', 'Las dos animaciones siguen un único audio y reloj.')
    .replace('Escuchar automático', 'Reproducir comparación');
  html = html.replace('</style>', '#baselinePlay,#baselineAudio,#baselineSeek{visibility:hidden!important}#model{display:none!important}</style>');
  html = html.replace('<main>', `<main><p><a href="../${escapeHtml(data.reviewFolder || 'forest-review-v1')}/index.html">Ver comparación de velocidades y decisiones automáticas</a></p>`);
  html = html.replace('Compará el ritmo actual con el ajuste por frase.', `Izquierda: ${beforeLabel}. Derecha: ${afterLabel}. Ambas animaciones usan exactamente la misma voz con velocidad automática y sus tiempos recalculados.`);
  html = html.replace('Escuchá una versión y después la otra; al iniciar una, la otra se detiene.', 'Reproducí el único audio de la derecha para observar simultáneamente ambos modelos.');
  html = html.replace('<label>Clasificación <select', '<label hidden>Clasificación <select')
    .replace('La velocidad del reproductor es normal (1×): la diferencia está en la voz generada.', 'El audio es idéntico en ambos lados y el reproductor permanece en 1×; sólo cambian las marcas del clasificador.');
} else if (data.directComparison) {
  html = html.replace('<main>', `<main><p><a href="../${data.directFolder || 'forest-direct-v1'}/index.html">Comparar ambos modelos simultáneamente con el mismo audio</a></p>`);
}
if (data.visualPolicies) {
  html = html.replace('<label>Voz <select', '<label>Versión nueva <select id="visualMode"><option value="labels">Sólo etiquetas revisadas</option><option value="loop">Etiquetas + empalme inglés candidato</option></select></label><br><br><label>Voz <select');
  html = html.replace(/<h1>.*?<\/h1>/, '<h1>Isa · etiquetas visuales y empalme del ciclo</h1>')
    .replace(/Izquierda:.*?Los objetivos de velocidad son experimentales\./,
      'Izquierda: recorrido actual. Derecha: apertura/cierre revisados; podés activar el empalme inglés candidato en Versión nueva. Ambos usan el mismo Random Forest, el mismo audio con velocidad automática y un solo reloj. La voz no se vuelve a generar en esta prueba.')
    .replace('sólo cambian las marcas del clasificador.', 'cambian las referencias visuales y el ciclo inglés; las marcas del clasificador son idénticas.')
    .replace('Los clasificadores fueron entrenados por separado; este visor no entrena mientras reproduce.', 'No se entrenó ningún clasificador: Random Forest permanece congelado.')
    .replace('Ambas usan el mismo banco y el mismo planificador temporal.', 'Ambas usan las mismas imágenes completas y el planificador temporal; la versión nueva revisa apertura/cierre y el empalme inglés.')
    .replace('Las etiquetas visuales y acústicas siguen siendo provisionales.', 'Apertura/cierre revisados por inspección del agente; forma fina provisional. No son etiquetas humanas certificadas. El español sólo prueba etiquetas; conserva su ciclo.')
    .replace('Ver comparación de velocidades y decisiones automáticas', 'Ver el relevamiento que originó esta prueba');
}
if(data.functionalityReview){
  html=html.replace(/<h1>.*?<\/h1>/,'<h1>Isa · revisión completa antes de entrenar</h1>')
    .replace(/Izquierda: recorrido actual\..*?La voz no se vuelve a generar en esta prueba\./,
      'Izquierda: renderer anterior y etiquetas anteriores. Derecha: renderer corregido y etiquetas revisadas. Ambos siguen el mismo Random Forest congelado y exactamente el mismo audio, que ya incluye el ajuste automático de velocidad por frase. El empalme inglés candidato sigue siendo opcional.')
    .replace('<h2 hidden>Decisiones automáticas</h2>','<h2>Ajustes de voz ya incluidos en el audio</h2>')
    .replace('<div class="table" hidden>','<div class="table">')
    .replace('Ritmo medido antes → después','Ritmo final de la frase')
    .replace('<h2>Actual · Random Forest</h2>','<h2>Referencia anterior</h2>')
    .replace('<h2>Revisión visual · Random Forest</h2>','<h2>Correcciones + etiquetas revisadas</h2>')
    .replace('</main>',`<h2>Recuperación y final de la lectura</h2>
      <p>Detené el audio para ver el fundido al reposo. Probá distintos instantes y compará ambos retratos.
      La referencia conserva el renderer y el manifiesto anteriores; la derecha incluye los arreglos de carga y cierre.</p>
      <p>Autoplay y servicio ocupado: los botones de recuperación y el reintento único se comprobaron con las pruebas de la app (45 frontend / 247 backend).
      Este visor reproduce WAV locales; no simula una respuesta real de Render ni llama al servicio de voz.</p>
      <p>La agrupación de marcas menores que un frame sigue pendiente. No se reentrenó ni cambió ningún modelo.</p></main>`);
  html=html.replace('<div class="pair">',`<div class="controls"><button id="finish">Detener lectura y ver cierre</button>
    <button id="recover">Probar fallo temporal de imágenes</button></div>
    <p id="recoveryStatus" role="status">La prueba de fallo reinicia los retratos, sin conexión externa. Mantené ambos retratos visibles para observar la recuperación.</p><div class="pair">`);
}
if(data.reviewedCatalogs)html=html.replace('<main>',
  '<main><p>Ambos modelos usan el renderer corregido y las mismas etiquetas visuales revisadas. Se conserva el ajuste de voz por frase y el reloj absoluto; sólo cambia la predicción del modelo. Las formas finas siguen siendo provisionales.</p>');
await writeFile(path.join(folder, 'index.html'), html);
console.log(path.join(folder, 'index.html'));
