// Read-only diagnostics for the actual final-test RF/TDNN animation paths.
import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { defaults, planTiming, labelsFor } from './timing_planner.mjs';
const frontend=path.resolve(process.argv[2]), folder=path.resolve(process.argv[3]);
const rows=JSON.parse(await readFile(process.argv[4],'utf8'));
const ranges=JSON.parse(await readFile(path.join(frontend,'src/app/shared/isabel/isa-speech-ranges.json'),'utf8'));
const result=[];
for (const language of ['es','en']) {
  const catalog=JSON.parse(await readFile(path.join(frontend,`src/app/shared/isabel/isa-speech-selection${language==='en'?'-en':''}.json`),'utf8'));
  const range=ranges[language], cycle=range.end-range.first;
  for (const row of rows.filter(r=>r.language===language)) for (const [version,cues] of Object.entries(row.versions)) {
    const plan=planTiming(cues,row.timing,catalog,range,defaults[language]);
    const frames=plan.frames.map(f=>range.first+(f-range.first)%cycle);
    const seams=frames.flatMap((f,i)=>i&&f<frames[i-1]?[{index:i,time:i/24,from:frames[i-1],to:f}]:[]);
    result.push({id:row.id,language,version,frames,wanted:plan.wanted,seams,
      provisionalShapes:labelsFor(catalog),advice_spans:row.advice_spans,
      timing:row.timing});
  }
}
await writeFile(path.join(folder,'animation-paths.json'),JSON.stringify(result));
console.log(JSON.stringify({plans:result.length,seams:result.reduce((n,r)=>n+r.seams.length,0)}));
