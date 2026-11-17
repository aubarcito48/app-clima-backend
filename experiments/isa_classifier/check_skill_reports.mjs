import assert from 'node:assert/strict';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { readFile, stat, writeFile } from 'node:fs/promises';
const frontend=path.resolve(process.argv[2]), root=path.resolve(process.argv[3]);
const { chromium, expect }=await import(pathToFileURL(path.join(frontend,'node_modules/@playwright/test/index.mjs')));
const browser=await chromium.launch();
const results=[];
try {
  for (const language of ['es','en']) {
    const folder=path.join(root,`audio/${language}-tdnn-test-01-automatic/prosody`);
    for (const name of ['report.html','report.md','prosody.json']) assert.ok((await stat(path.join(folder,name))).size>0);
    const page=await browser.newPage({viewport:{width:1366,height:900}});
    const errors=[],remote=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('request',r=>{if (/^https?:/.test(r.url())) remote.push(r.url());});
    await page.goto(pathToFileURL(path.join(folder,'report.html')).href);
    await page.locator('#playPause').click();
    await expect.poll(()=>page.locator('#audio').evaluate(a=>a.currentTime)).toBeGreaterThan(.3);
    await page.locator('#playPause').click();
    await page.locator('#audio').evaluate(a=>{a.pause();a.currentTime=2;});
    await expect.poll(()=>page.locator('#audio').evaluate(a=>a.currentTime)).toBeGreaterThan(1.9);
    await page.locator('#nextMoment').click();
    await page.locator('#setLoopHere').click();
    await page.locator('#togglePauses').uncheck();
    await page.locator('#togglePauses').check();
    await page.locator('#togglePeaks').uncheck();
    await page.locator('#togglePeaks').check();
    for(const layout of ['Map','Card','Library']) {
      await page.getByRole('button',{name:layout,exact:true}).click();
      const pending=page.waitForEvent('download');
      await page.locator('#downloadVisualImage').click();
      const download=await pending;
      const bytes=await readFile(await download.path());
      assert.ok(bytes.length>1000);
      assert.equal(bytes.subarray(1,4).toString(),'PNG');
    }
    await page.locator('#visualOnlyToggle').click();
    await page.screenshot({path:path.join(root,`prosody-screen-${language}.png`),fullPage:true});
    await page.setViewportSize({width:390,height:844});
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
    assert.deepEqual(errors,[]);assert.deepEqual(remote,[]);
    results.push({language,playback:true,seeking:true,toggles:true,png_exports:true,mobile_overflow:overflow,errors,remote});
    await page.close();
  }
} finally {await browser.close();}
await writeFile(path.join(root,'report-ui-check.json'),JSON.stringify(results,null,2));
console.log(JSON.stringify(results));
