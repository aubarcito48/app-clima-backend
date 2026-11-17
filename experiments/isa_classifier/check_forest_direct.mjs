import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
const frontend = path.resolve(process.argv[2]), folder = path.resolve(process.argv[3]);
const { chromium, expect } = await import(pathToFileURL(path.join(frontend, 'node_modules/@playwright/test/index.mjs')));
const data = JSON.parse(await readFile(path.join(folder, 'comparison.json'), 'utf8'));
assert.equal(data.compareModels, true);
for (const sample of data.cases) {
  assert.equal(sample.baseline.audio, sample.automatic.audio);
  assert.equal(sample.baseline.sha256_pcm, sample.automatic.sha256_pcm);
  assert.equal(sample.baseline.forcedModel, 'previous'); assert.equal(sample.automatic.forcedModel, 'balanced');
}
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1366, height: 1000 } });
  const errors = [], remote = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('request', r => { if (/^https?:/.test(r.url())) remote.push(r.url()); });
  await page.goto(pathToFileURL(path.join(folder, 'index.html')).href);
  for (const language of ['en', 'es']) {
    await page.locator('#language').selectOption(language);
    await expect(page.locator('#automaticPlay')).toBeEnabled();
    await expect(page.getByRole('heading', { name: data.models.previous, exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: data.models.balanced, exact: true })).toBeVisible();
    await expect(page.locator('#baselineAudio')).toBeHidden();
    await page.locator('#automaticPlay').click();
    await expect.poll(() => page.locator('#automaticAudio').evaluate(a => a.currentTime)).toBeGreaterThan(.7);
    for (const name of ['baseline', 'automatic']) {
      await expect(page.locator('#'+name+' canvas')).toHaveAttribute('data-isa-speaking', 'true');
      await expect(page.locator('#'+name+' canvas')).toHaveAttribute('data-isa-speech-language', language);
    }
    await page.locator('#automaticAudio').evaluate(a => { a.pause(); a.currentTime = 2.5; });
    for (const name of ['baseline', 'automatic']) await expect(page.locator('#'+name+'Time')).toContainText('2.500');
    assert.equal(await page.locator('#baseline').getAttribute('data-audio-time'), await page.locator('#automatic').getAttribute('data-audio-time'));
    for (const name of ['baseline', 'automatic']) assert.ok(await page.locator('#'+name+'Bars').evaluate(c => c.getContext('2d').getImageData(0,0,c.width,c.height).data.some((v,i) => i%4===3 && v)));
    await page.screenshot({ path: path.join(folder, `models-${language}.png`), fullPage: true });
    const values = await page.locator('#scenario option').evaluateAll(options => options.map(o => o.value));
    await page.locator('#scenario').selectOption(values.at(-1));
    await expect(page.locator('#automaticPlay')).toBeEnabled();
  }
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  await page.screenshot({ path: path.join(folder, 'models-mobile.png'), fullPage: true });
  assert.deepEqual(errors, []); assert.deepEqual(remote, []);
  console.log('Direct model comparison ES/EN: identical PCM, one master clock/audio, portraits, bars, seeking, new samples, mobile, offline: OK');
} finally { await browser.close(); }
