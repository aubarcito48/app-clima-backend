import assert from 'node:assert/strict';
import { readFile,writeFile } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { planTiming,defaults } from './timing_planner.mjs';
const frontend=path.resolve(process.argv[2]),folder=path.resolve(process.argv[3]);
const {chromium,expect}=await import(pathToFileURL(path.join(frontend,'node_modules/@playwright/test/index.mjs')));
const data=JSON.parse(await readFile(path.join(folder,'comparison.json'),'utf8'));
for(const row of data.cases){
  assert.equal(row.baseline.audio,row.automatic.audio);
  assert.equal(row.baseline.sha256_pcm,row.automatic.sha256_pcm);
  assert.deepEqual(row.automatic.model_cues.previous,row.automatic.model_cues.balanced);
}
const browser=await chromium.launch(),checks=[];
try{
 const page=await browser.newPage({viewport:{width:1366,height:1000}}),errors=[],remote=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))remote.push(r.url());});
 await page.goto(pathToFileURL(path.join(folder,'index.html')).href);
 for(const language of ['en','es'])for(const mode of ['labels','loop']){
  await page.locator('#language').selectOption(language);await page.locator('#visualMode').selectOption(mode);
  await expect(page.locator('#automaticPlay')).toBeEnabled();
  const id=await page.locator('#scenario').inputValue();const row=data.cases.find(r=>r.language===language&&r.id===id);
  for(const name of ['baseline','automatic']){
   const policy=data.visualPolicies[name],catalog=structuredClone(policy.catalogs[language]);
   const range=mode==='labels'?data.visualPolicies.baseline.ranges[language]:policy.ranges[language];
   if(mode==='labels')delete catalog.reviewedLoop;
   const plan=planTiming(row.automatic.model_cues.previous,row.automatic.timing,catalog,range,defaults[language]);
   const canvas=page.locator('#'+name+' canvas');
   await expect(canvas).toHaveAttribute('data-range-first',String(range.first));
   await expect(canvas).toHaveAttribute('data-range-end',String(range.end));
   for(const t of [2.5,6.9,7.1,7.4]){
    await page.locator('#automaticAudio').evaluate((a,t)=>{a.pause();a.currentTime=t;},t);
    await expect(page.locator('#'+name+'Time')).toContainText(t.toFixed(3));
    const expected=range.first+Math.floor(plan.sourceSecondsAt(t)*24)%(range.end-range.first);
    await expect.poll(async()=>Math.abs(Number(await canvas.getAttribute('data-atlas-frame'))-expected)).toBeLessThanOrEqual(1);
   }
  }
  const sig=await page.locator('#automatic').getAttribute('data-plan-signature');
  await page.locator('#accelerate').setChecked(!defaults[language].avoidLongClosures);
  await page.locator('#accelerate').setChecked(defaults[language].avoidLongClosures);
  await expect(page.locator('#automatic')).toHaveAttribute('data-plan-signature',sig);
  await page.locator('#automaticPlay').click();
  await expect.poll(()=>page.locator('#automaticAudio').evaluate(a=>a.currentTime)).toBeGreaterThan(.4);
  await page.locator('#automaticAudio').evaluate(a=>{a.pause();a.currentTime=7.4;});
  for(const name of ['baseline','automatic'])await expect(page.locator('#'+name+'Time')).toContainText('7.400');
  await page.screenshot({path:path.join(folder,`visual-${language}-${mode}.png`),fullPage:true});
  checks.push({language,mode,same_audio:true,same_RF:true,renderer_ranges:true,renderer_frames:true,absolute_seeking:true});
 }
 await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await page.screenshot({path:path.join(folder,'visual-mobile.png'),fullPage:true});
 assert.deepEqual(errors,[]);assert.deepEqual(remote,[]);
}finally{await browser.close();}
await writeFile(path.join(folder,'viewer-check.json'),JSON.stringify(checks,null,2));
console.log('Visual comparison: same RF/PCM, independent renderer ranges/actual frames, both modes and languages, seeking across seams, playback/mobile/offline: OK');
