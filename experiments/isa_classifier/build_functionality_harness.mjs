// Bundle the unmodified portrait with inline copies of its existing assets.
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const frontend=path.resolve(process.argv[2]),out=path.resolve(process.argv[3]);await mkdir(out,{recursive:true});
const {build}=await import(pathToFileURL(path.join(frontend,'node_modules/esbuild/lib/main.js')));
const result=await build({stdin:{contents:`import {createIsaPortrait} from './src/app/shared/isabel/isa-portrait.ts';
window.boot=async()=>{window.controller?.destroy();document.querySelector('#portrait').replaceChildren();window.controller=await createIsaPortrait(document.querySelector('#portrait'));return true;};
window.boot().then(()=>window.ready=true);`,resolveDir:frontend},bundle:true,format:'iife',write:false,plugins:[{name:'inline-atlases',setup(b){
 b.onLoad({filter:/isa-(portrait|speech)-manifest(?:-en)?\.json$/},async({path:file})=>{
  const data=JSON.parse(await readFile(file,'utf8'));
  const image=async name=>'data:image/webp;base64,'+(await readFile(path.join(frontend,'public',name))).toString('base64')+'#'+path.basename(name);
  if(data.image)data.image=await image(data.image);for(const page of data.pages??[])page.image=await image(page.image);
  return {contents:JSON.stringify(data),loader:'json'};
 });
}}]});
await writeFile(path.join(out,'portrait-harness.html'),`<!doctype html><html lang="es"><meta charset="utf-8"><title>Isa · funciones del retrato publicado</title><style>body{background:#edf8fc;color:#123952;font:16px system-ui;margin:24px}#portrait{width:320px;height:320px}</style><h1>Isa · revisión funcional del retrato</h1><div id="portrait"></div><script>${result.outputFiles[0].text.replaceAll('</script','<\\/script')}</script></html>`);
console.log(path.join(out,'portrait-harness.html'));
