import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { access } from 'node:fs/promises';
import assert from 'node:assert/strict';
const frontend=path.resolve(process.argv[2]), root=path.resolve(process.argv[3]);
const { chromium, expect }=await import(pathToFileURL(path.join(frontend,'node_modules/@playwright/test/index.mjs')));
const browser=await chromium.launch();
try {
  const page=await browser.newPage({viewport:{width:1366,height:900}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.join(root,'index.html')).href);
  await expect(page.getByRole('heading',{level:1})).toContainText('Isa');
  for (const href of await page.locator('a').evaluateAll(a=>a.map(x=>x.getAttribute('href')))) {
    assert.ok(!/^https?:/.test(href));await access(path.resolve(root,href));
  }
  await page.locator('details summary').first().click();
  assert.ok(await page.locator('details img').first().evaluate(img=>img.complete&&img.naturalWidth>0));
  await page.screenshot({path:path.join(root,'audit-desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.screenshot({path:path.join(root,'audit-mobile.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  console.log('Evidence index: local links, contact sheet, mobile layout and console OK');
} finally {await browser.close();}
