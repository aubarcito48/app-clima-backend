import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import path from 'node:path';
const frontend=path.resolve(process.argv[2]), input=path.resolve(process.argv[3]), output=path.resolve(process.argv[4]);
await mkdir(output,{recursive:true});
const data=JSON.parse(await readFile(path.join(input,'comparison.json'),'utf8'));
const baselineCommit=execFileSync('git',['rev-parse','HEAD'],{cwd:frontend,encoding:'utf8'}).trim();
data.functionalityReview={baselineCommit,scope:'Frozen RF/PCM, prior and corrected renderer, reviewed visual labels; no training'};
data.models={previous:'Referencia anterior',balanced:'Correcciones + etiquetas revisadas'};
data.reviewFolder='functionality-audit-v1';
for(const row of data.cases){
  row.label=row.id.endsWith('original')?'Referencia de lluvia':`Consejo reservado ${row.id.endsWith('01')?'1':'2'}`;
  if(row.baseline.audio!==row.automatic.audio)throw Error('Audio differs');
  const bytes=Buffer.from(row.automatic.audio.split(',')[1],'base64');
  const digest=createHash('sha256').update(bytes).digest('hex');
  row.reviewAudioSha256=digest;
  if(JSON.stringify(row.baseline.model_cues.previous)!==JSON.stringify(row.automatic.model_cues.balanced))throw Error('RF marks differ');
}
await writeFile(path.join(output,'comparison.json'),JSON.stringify(data));
await writeFile(path.join(output,'provenance.json'),JSON.stringify({baselineCommit,
  source:path.relative(output,input),training:false,cases:data.cases.map(r=>({id:r.id,language:r.language,wavSha256:r.reviewAudioSha256,pcmSha256:r.automatic.sha256_pcm}))},null,2));
console.log(JSON.stringify({cases:data.cases.length,baselineCommit,training:false}));
