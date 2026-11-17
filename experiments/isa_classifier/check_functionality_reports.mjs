import path from 'node:path';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const frontend=path.resolve(process.argv[2]), root=path.resolve(process.argv[3]);
const {chromium}=await import(pathToFileURL(path.join(frontend,'node_modules/@playwright/test/index.mjs')));
const browser=await chromium.launch();
try {
  const page=await browser.newPage();
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  for(const lang of ['es','en']) {
    await page.goto(pathToFileURL(path.join(root,'micro-prosody',lang,'report.html')).href);
    await page.locator('audio').first().evaluate(async audio=>{
      await audio.play();
      await new Promise(resolve=>setTimeout(resolve,200));
      if(audio.currentTime<=0) throw new Error('Audio did not advance');
      audio.pause();audio.currentTime=1;
    });
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    await page.screenshot({path:path.join(root,`micro-prosody-${lang}-mobile.png`),fullPage:true});
    console.log(`${lang}: local audio playback, seeking and mobile layout OK`);
  }
  assert.deepEqual(errors,[]);
} finally {await browser.close();}
