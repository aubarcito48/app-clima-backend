import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const frontend = path.resolve(process.argv[2]), folder = path.resolve(process.argv[3]);
const source = path.dirname(fileURLToPath(import.meta.url));
const { build } = await import(pathToFileURL(path.join(frontend, 'node_modules/esbuild/lib/main.js')));
const data = JSON.parse(await readFile(path.join(folder, 'timing.json'), 'utf8'));
data.catalogs = {};
for (const language of ['es', 'en']) data.catalogs[language] = JSON.parse(await readFile(
  path.join(frontend, `src/app/shared/isabel/isa-speech-selection${language === 'en' ? '-en' : ''}.json`), 'utf8'));
data.ranges = JSON.parse(await readFile(path.join(frontend, 'src/app/shared/isabel/isa-speech-ranges.json'), 'utf8'));
const result = await build({ entryPoints: [path.join(source, 'timing_lab_entry.mjs')], bundle: true,
  write: false, format: 'iife', target: 'es2022', platform: 'browser', plugins: [{ name: 'offline-isa', setup(b) {
    b.onResolve({ filter: /^isa\/(portrait|playback)$/ }, args => ({ path: path.join(frontend, `src/app/shared/isabel/isa-${args.path.split('/')[1]}.ts`) }));
    b.onResolve({ filter: /^isa\/timing-data$/ }, () => ({ path: 'data', namespace: 'timing' }));
    b.onLoad({ filter: /.*/, namespace: 'timing' }, () => ({ contents: JSON.stringify(data), loader: 'json' }));
    b.onLoad({ filter: /isa-(portrait|speech)-manifest(?:-en)?\.json$/ }, async ({ path: file }) => {
      const manifest = JSON.parse(await readFile(file, 'utf8'));
      const image = async name => 'data:image/webp;base64,' + (await readFile(path.join(frontend, 'public', name))).toString('base64');
      if (manifest.image) manifest.image = await image(manifest.image);
      for (const page of manifest.pages ?? []) page.image = await image(page.image);
      return { contents: JSON.stringify(manifest), loader: 'json' };
    });
  } }] });
const template = await readFile(path.join(source, 'timing_lab.html'), 'utf8');
const version = data.rightVersion ?? Object.keys(data.cases[0].versions)[0];
if (!/^v\d+$/.test(version)) throw Error('Invalid timing model version');
const label = version === 'v9' ? 'Híbrido entrenado (experimental)'
  : version === 'v8' ? 'Fonemas Piper (experimental)' : version.toUpperCase();
let html = template.replaceAll('V6', label);
if (data.integrated) {
  html = html.replace('<blockquote id="text">',
    '<div class="controls"><label>Marcas del ensayo <select id="timingModel"></select></label></div>'
    + '<p>Compará la boca con la voz. Ambos lados pueden usar el mismo planificador temporal: '
    + 'el control V7 usa sus marcas acústicas y el ensayo permite elegir las variantes disponibles. '
    + 'Se conservan energía, pausas, desfases, apertura/cierre y aceleración de cierres largos. '
    + (version === 'v9'
      ? 'El híbrido sí fue entrenado con señales de voz, tiempos y fonemas; las otras opciones sirven de referencia.</p><blockquote id="text">'
      : 'Esto compara alternativas; todavía no fusiona ni reentrena sus modelos.</p><blockquote id="text">'));
  html = html.replace('<select id="referenceSource">',
    '<select id="referenceSource"><option value="v7-timed">V7 + ajustes temporales</option>');
  html = html.replace('<h2>Selector actual · control</h2>', '<h2 id="referenceTitle">V7 + tiempos · control</h2>')
    .replace(`<h2>${label} · tiempos experimentales</h2>`, '<h2 id="ownTitle">Ensayo + tiempos</h2>');
}
await writeFile(path.join(folder, 'index.html'), html
  .replace('/*BUNDLE*/', result.outputFiles[0].text.replaceAll('</script', '<\\/script')));
console.log(path.join(folder, 'index.html'));
