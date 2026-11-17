import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const frontend=path.resolve(process.argv[2]),folder=path.resolve(process.argv[3]);
const {chromium,expect}=await import(pathToFileURL(path.join(frontend,'node_modules/@playwright/test/index.mjs')));
const data=JSON.parse(await readFile(path.join(folder,'comparison.json'),'utf8'));
const browser=await chromium.launch(),checks=[];
try{
 const page=await browser.newPage({viewport:{width:1366,height:1000}}),errors=[],remote=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))remote.push(r.url());});
 await page.goto(pathToFileURL(path.join(folder,'index.html')).href);
 for(const language of ['en','es']){
  await page.locator('#language').selectOption(language);
  await expect(page.locator('#automaticPlay')).toBeEnabled();
  for(const row of data.cases.filter(r=>r.language===language)){
   await page.locator('#scenario').selectOption(row.id);
   await expect(page.locator('#automaticPlay')).toBeEnabled();
   await expect(page.locator('#text')).toHaveText(row.text);
   for(const name of ['baseline','automatic']){
    await expect(page.locator('#'+name+'Bars')).toBeVisible();
    const painted=await page.locator('#'+name+'Bars').evaluate(c=>c.getContext('2d').getImageData(0,0,c.width,c.height).data.some((v,i)=>i%4===3&&v>0));
    assert.ok(painted);
   }
   await page.locator('#automaticPlay').click();
   await expect.poll(()=>page.locator('#automaticAudio').evaluate(a=>a.currentTime)).toBeGreaterThan(.2);
   await page.locator('#automaticAudio').evaluate(a=>{a.pause();a.currentTime=4.5;});
   await expect(page.locator('#automaticTime')).toContainText('4.500');
   await expect(page.locator('#baselineTime')).toContainText('4.500');
   await expect(page.locator('#automaticTime')).toContainText('4.500');
   await page.locator('#finish').click();
   await page.locator('#automatic canvas').scrollIntoViewIfNeeded();
   for(const name of ['baseline','automatic'])
    await expect.poll(async()=>Number(await page.locator('#'+name+' canvas').getAttribute('data-isa-speech-blend'))).toBe(0);
   checks.push({case:row.id,playback:true,bars:true,shared_clock:true});
  }
  await page.locator('#recover').click();
  await expect(page.locator('#recoveryStatus')).toHaveAttribute('data-result','pass',{timeout:15000});
  await expect(page.locator('#recover')).toBeEnabled();
  await expect(page.locator('#automaticPlay')).toBeEnabled();
  await page.screenshot({path:path.join(folder,`complete-${language}.png`),fullPage:true});
  checks.push({language,recovery_before_fails_after_recovers:true});
 }
 await page.setViewportSize({width:390,height:844});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await page.screenshot({path:path.join(folder,'complete-mobile.png'),fullPage:true});
 assert.deepEqual(errors,[]);assert.deepEqual(remote,[]);
}finally{await browser.close();}
await writeFile(path.join(folder,'functional-viewer-check.json'),JSON.stringify(checks,null,2));
console.log(JSON.stringify({cases:6,recovery_languages:2,offline:true,mobile:true,errors:0}));
