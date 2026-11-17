import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { defaults, planTiming, speechEvidence } from './timing_planner.mjs';
const folder=path.resolve(process.argv[2]), batch=JSON.parse(await readFile(process.argv[3],'utf8'));
const data=JSON.parse(await readFile(path.join(folder,'comparison.json'),'utf8'));
const frozen=process.argv[4]?JSON.parse(await readFile(process.argv[4],'utf8')):null;
const results=[];
for(const row of batch){
  const l=row.language, before=data.visualPolicies.baseline, after=data.visualPolicies.automatic;
  const labelsOnly=structuredClone(after.catalogs[l]);delete labelsOnly.reviewedLoop;
  const variants={before:[before.catalogs[l],before.ranges[l]],labels:[labelsOnly,before.ranges[l]],after:[after.catalogs[l],after.ranges[l]]};
  const plans={}, actual={};
  for(const [name,[catalog,range]] of Object.entries(variants)){
    const plan=planTiming(row.versions.previous,row.timing,catalog,range,defaults[l]);plans[name]=plan;
    const cycle=range.end-range.first;
    actual[name]=plan.frames.map(f=>range.first+(f-range.first)%cycle);
    for(let i=1;i<plan.frames.length;i++){
      const step=plan.frames[i]-plan.frames[i-1];
      assert.ok(step>=0&&step<=5);assert.ok(Math.abs(plan.frames[i]-range.first-i)<=defaults[l].maxDrift);
      if(step>=2){
        const from=actual[name][i-1],to=actual[name][i],jump=catalog.jumps[String(from)]?.[step-2];
        assert.ok(to>from&&jump&&jump.pose<=.04&&jump.motion<=.025);
      }
      if(actual[name][i]<actual[name][i-1]&&catalog.reviewedLoop){
        assert.equal(actual[name][i-1],catalog.reviewedLoop.end-1);assert.equal(actual[name][i],catalog.reviewedLoop.first);
      }
    }
    let previous=-1;
    for(let i=0;i<=Math.ceil(row.timing.duration*120);i++){
      const t=Math.min(row.timing.duration,i/120),source=plan.sourceSecondsAt(t);
      assert.ok(source>=previous-1e-8);previous=source;
      assert.equal(plan.sourceSecondsAt(t),source);
    }
  }
  if(frozen){
    const original=frozen.find(r=>r.id===row.id&&r.version==='previous');
    assert.ok(original);assert.deepEqual(actual.before,original.frames,'Old policy changed relative to frozen audit');
  }
  for(const name of ['labels','after']){
    const result={id:row.id,language:l,variant:name,advice_total:0,advice_paired_known:0,active_open_requests:0,
      closed_before:0,closed_after:0,pause_total:0,pause_paired_known:0,pause_closed_before:0,pause_closed_after:0};
    const states=after.catalogs[l].mouthStates;
    for(let i=0;i<plans.before.frames.length;i++){
      const t=(i+.5)/24, a=states[actual.before[i]],b=states[actual[name][i]];
      const known=Object.values(actual).every(indices=>states[indices[i]]!=='uncertain');
      const pause=row.timing.inserted_pauses.some(p=>p.start<=t&&t<p.end);
      if(pause){
        result.pause_total++;
        if(known){result.pause_paired_known++;result.pause_closed_before+=a==='closed';result.pause_closed_after+=b==='closed';}
      }
      if(!pause&&row.advice_spans.some(([start,end])=>start<=t&&t<end)){
        result.advice_total++;
        if(known){
          result.advice_paired_known++;
          if(plans.before.wanted[i]!=='X'&&speechEvidence(row.timing,t)){
            result.active_open_requests++;result.closed_before+=a==='closed';result.closed_after+=b==='closed';
          }
        }
      }
    }
    results.push(result);
  }
}
const report={note:'same RF and original PCM; paired times with agent-reviewed binary states on both sides; not model accuracy or human gold',cases:results,summary:{}};
for(const l of ['es','en'])for(const name of ['labels','after']){
  const subset=results.filter(r=>r.language===l&&r.variant===name),sum={};
  for(const key of Object.keys(subset[0]).filter(k=>typeof subset[0][k]==='number'))sum[key]=subset.reduce((n,r)=>n+r[key],0);
  sum.closed_before_rate=sum.closed_before/sum.active_open_requests;sum.closed_after_rate=sum.closed_after/sum.active_open_requests;
  sum.pause_closed_before_rate=sum.pause_closed_before/sum.pause_paired_known;sum.pause_closed_after_rate=sum.pause_closed_after/sum.pause_paired_known;
  sum.paired_advice_coverage=sum.advice_paired_known/sum.advice_total;
  sum.recordings=subset.length;report.summary[`${l}-${name}`]=sum;
}
await writeFile(path.join(folder,'evaluation.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify(report.summary));
