import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const frontend=path.resolve(process.argv[2]),out=path.resolve(process.argv[3]);
const {chromium,expect}=await import(pathToFileURL(path.join(frontend,'node_modules/@playwright/test/index.mjs')));
const atlas=JSON.parse(await readFile(path.join(frontend,'src/app/shared/isabel/isa-portrait-manifest.json'),'utf8'));
await mkdir(path.join(out,'captures'),{recursive:true});
const browser=await chromium.launch(),checks=[],errors=[];
try{
 const page=await browser.newPage({viewport:{width:900,height:700}});
 await page.clock.install();
 await page.addInitScript(()=>{
  Math.random=()=>0;window.imageLoads=[];window.failSpeech=false;
  const decode=Image.prototype.decode;
  Image.prototype.decode=function(){
   const tag=this.src.split('#')[1]??'unknown';window.imageLoads.push(tag);
   if(window.failSpeech&&tag.includes('speech'))return Promise.reject(Error('Simulated temporary atlas failure'));
   return decode.call(this);
  };
  window.framesPending=new Set();const raf=requestAnimationFrame,caf=cancelAnimationFrame;
  window.requestAnimationFrame=fn=>{let id;id=raf(t=>{window.framesPending.delete(id);fn(t)});window.framesPending.add(id);return id;};
  window.cancelAnimationFrame=id=>{window.framesPending.delete(id);caf(id);};
 });
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(pathToFileURL(path.join(out,'portrait-harness.html')).href);
 await page.waitForFunction(()=>window.ready);
 const canvas=page.locator('#portrait canvas');
 const run=async ms=>{await page.clock.runFor(ms);};
 const snapshot=async name=>{await canvas.screenshot({path:path.join(out,'captures',name+'.png')});return canvas.evaluate(c=>({...c.dataset}));};
 for(const pose of ['isa-awake','isa-right','isa-down','isa-sleep','isa-awake']){
  await page.evaluate(p=>window.controller.play(p),pose);await run(2200);
  await expect(canvas).toHaveAttribute('data-isa-expression',pose);
  checks.push({feature:'pose',pose,pass:true,state:await snapshot('pose-'+pose)});
 }
 await page.evaluate(()=>window.controller.play('isa-awake'));await run(4620);
 const blink=await snapshot('idle-blink');assert.ok(atlas.blink.includes(Number(blink.isaFrame)));
 checks.push({feature:'idle-blink',pass:true,state:blink});await run(600);
 for(const language of ['en','es']){
  await page.evaluate(l=>{window.controller.setSpeechLanguage(l);window.controller.setWorking(true);},language);
  await page.waitForFunction(()=>document.querySelector('canvas')&&window.imageLoads.some(x=>x.includes('speech')));
  await page.evaluate(()=>{window.controller.setSpeaking(true);window.controller.setSpeechTime(1);});await run(800);
  await expect.poll(()=>canvas.getAttribute('data-isa-speech-blend')).toMatch(/^0\.99|^1\.000/);
  const before=Number(await canvas.getAttribute('data-isa-speech-frame'));
  await page.evaluate(()=>{window.controller.setMouthOpening(0);window.controller.play('isa-down');window.controller.setWorking(true);});await run(300);
  assert.equal(Number(await canvas.getAttribute('data-isa-speech-frame')),before);
  await expect(canvas).toHaveAttribute('data-isa-expression','isa-awake');
  checks.push({feature:'speech-clock-and-quiet',language,pass:true,state:await snapshot('speech-'+language)});
  await page.evaluate(t=>window.controller.setSpeechTime(t),language==='es'?4.5:4);await run(500);
  await page.evaluate(()=>window.controller.setSpeaking(false));await run(100);
  const fade=Number(await canvas.getAttribute('data-isa-speech-blend'));assert.ok(fade>0&&fade<1);
  await snapshot('ending-'+language+'-100ms');await run(1100);
  if (process.argv.includes('--expect-fixes') && language === 'es')
    assert.equal(Number(await canvas.getAttribute('data-isa-speech-frame')),126);
  assert.equal(Number(await canvas.getAttribute('data-isa-speech-blend')),0);
  checks.push({feature:'ending-fade',language,pass:true,blend_at_100ms:fade,
    final_source_frame:Number(await canvas.getAttribute('data-isa-speech-frame'))});
 }
 await page.evaluate(()=>{window.controller.setSpeaking(false);window.controller.setWorking(false);window.controller.setExpression('isa-awake');});
 const loadsBefore=await page.evaluate(()=>window.imageLoads.length);
 await page.evaluate(()=>{window.controller.setWorking(true);window.controller.setSpeaking(true);});await run(1200);
 assert.equal(Number(await canvas.getAttribute('data-isa-speech-blend')),0);
 assert.equal(await page.evaluate(()=>window.imageLoads.length),loadsBefore);
 checks.push({feature:'reduced-motion',pass:true,state:await snapshot('reduced-motion')});
 await page.evaluate(()=>{window.controller.play('isa-awake');window.controller.setSpeechTime(1);});await run(600);
 const hiddenFrame=await canvas.getAttribute('data-isa-speech-frame');
 await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));});await run(1000);
 assert.equal(await canvas.getAttribute('data-isa-speech-frame'),hiddenFrame);
 assert.equal(await page.evaluate(()=>window.framesPending.size),0);
 await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'));window.controller.setSpeechTime(3);});await run(500);
 assert.notEqual(await canvas.getAttribute('data-isa-speech-frame'),hiddenFrame);
 checks.push({feature:'simulated-hidden-resume',pass:true});
 await page.evaluate(()=>{window.controller.destroy();window.failSpeech=true;});await page.evaluate(()=>window.boot());
 await page.evaluate(()=>{window.controller.play('isa-awake');window.controller.setWorking(true);window.controller.setSpeaking(true);});await run(800);
 assert.equal(Number(await canvas.getAttribute('data-isa-speech-blend')),0);
 await snapshot('speech-atlas-failed');
 const failures=await page.evaluate(()=>window.imageLoads.filter(x=>x.includes('speech')).length);
 await page.evaluate(()=>{window.failSpeech=false;window.controller.setSpeaking(false);window.controller.setWorking(false);});await run(400);
 await page.evaluate(()=>{window.controller.setWorking(true);window.controller.setSpeaking(true);window.controller.setSpeechTime(1);});await run(800);
 const retries=await page.evaluate(()=>window.imageLoads.filter(x=>x.includes('speech')).length)-failures;
 if (process.argv.includes('--expect-fixes')) {
  assert.ok(retries>0);
  assert.ok(Number(await canvas.getAttribute('data-isa-speech-blend'))>.99);
 }
 checks.push({feature:'temporary-atlas-failure-retry',observed_retry_attempts:retries,
  speech_blend:Number(await canvas.getAttribute('data-isa-speech-blend')),finding:retries===0?'failure persists for next same-language narration':'retried'});
 await page.evaluate(()=>{window.controller.setSpeaking(false);window.controller.setWorking(false);window.controller.setSpeechLanguage('en');window.controller.setWorking(true);window.controller.setSpeaking(true);window.controller.setSpeechTime(1);});await run(800);
 assert.ok(Number(await canvas.getAttribute('data-isa-speech-blend'))>.99);
 checks.push({feature:'atlas-recovery-after-language-reset',pass:true});
 await page.evaluate(()=>window.controller.destroy());await run(2000);
 assert.equal(await page.locator('canvas').count(),0);assert.equal(await page.evaluate(()=>window.framesPending.size),0);
 checks.push({feature:'destroy-cleanup',pass:true});assert.deepEqual(errors,[]);
}finally{await browser.close();}
await writeFile(path.join(out,'portrait-functions.json'),JSON.stringify({method:'unmodified production portrait, real assets; virtual browser clock; controlled atlas failure and visibility',checks,errors},null,2));
console.log(JSON.stringify(checks.map(({state,...rest})=>rest)));
