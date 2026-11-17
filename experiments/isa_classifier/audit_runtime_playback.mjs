// Audit the actual app playback code, not the experimental planner.
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const frontend=path.resolve(process.argv[2]),corpus=path.resolve(process.argv[3]),out=path.resolve(process.argv[4]);
await mkdir(out,{recursive:true});
const {build}=await import(pathToFileURL(path.join(frontend,'node_modules/esbuild/lib/main.js')));
await build({stdin:{contents:"export {createIsaPlayback} from './src/app/shared/isabel/isa-playback.ts';",resolveDir:frontend},bundle:true,platform:'node',format:'esm',outfile:path.join(out,'production-playback.mjs')});
const {createIsaPlayback}=await import(pathToFileURL(path.join(out,'production-playback.mjs')));
const manifest=JSON.parse(await readFile(corpus,'utf8')),results=[];
for(const row of manifest.recordings.filter(r=>r.split==='test'&&r.evaluation==='fresh')){
 const bytes=await readFile(path.join(path.dirname(corpus),row.file)),buffer=bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength);
 const playback=createIsaPlayback(buffer,row.language);
 if(!playback)throw Error('Unexpected playback rejection: '+row.id);
 const reversals=[];let previous=playback.sourceSecondsAt(0),maxLag=0,maxLead=0;
 for(let i=1;i<=Math.ceil(playback.duration*120);i++){
  const t=Math.min(playback.duration,i/120),phase=playback.sourceSecondsAt(t);
  if(phase<previous-1e-7)reversals.push({time:t,previous,phase,backward_ms:(previous-phase)*1000});
  maxLag=Math.max(maxLag,t-phase);maxLead=Math.max(maxLead,phase-t);previous=phase;
 }
 let holdPairs=0;for(const cycle of playback.cycles)for(let i=1;i<cycle.length;i++)holdPairs+=cycle[i]===cycle[i-1];
 results.push({id:row.id,language:row.language,duration:row.duration,hold_pairs:holdPairs,
  acoustic_pauses:playback.pauses.length,micro_pauses:playback.micro.length,
  max_lag_ms:maxLag*1000,max_lead_ms:maxLead*1000,reversals,
  nonfinite_returns_zero:playback.sourceSecondsAt(NaN)===0,
  stateless_seek:playback.sourceSecondsAt(2)===playback.sourceSecondsAt(2)});
}
const summary={};for(const lang of ['es','en']){
 const rows=results.filter(r=>r.language===lang);
 summary[lang]={recordings:rows.length,with_backwards_clock:rows.filter(r=>r.reversals.length).length,
  backwards_steps:rows.reduce((n,r)=>n+r.reversals.length,0),
  largest_backwards_ms:Math.max(0,...rows.flatMap(r=>r.reversals.map(x=>x.backward_ms))),
  max_lag_ms:Math.max(...rows.map(r=>r.max_lag_ms)),max_lead_ms:Math.max(...rows.map(r=>r.max_lead_ms)),
  known_pause_minmax:[Math.min(...rows.map(r=>r.acoustic_pauses)),Math.max(...rows.map(r=>r.acoustic_pauses))]};
}
const invalidRejected=createIsaPlayback(new ArrayBuffer(44),'en')===undefined;
await writeFile(path.join(out,'runtime-playback.json'),JSON.stringify({note:'unmodified app playback; original Rhubarb WAV cues, not RF lab cues',summary,invalidRejected,cases:results},null,2));
console.log(JSON.stringify({summary,invalidRejected}));
