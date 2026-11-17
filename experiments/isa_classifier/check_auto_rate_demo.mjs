import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
const frontend = path.resolve(process.argv[2]), folder = path.resolve(process.argv[3]);
const { chromium, expect } = await import(pathToFileURL(path.join(frontend, 'node_modules/@playwright/test/index.mjs')));
const data = JSON.parse(await readFile(path.join(folder, 'comparison.json'), 'utf8'));
for (const sample of data.cases) {
  assert.equal(sample.baseline.text, sample.automatic.text);
  assert.notEqual(sample.baseline.sha256_pcm, sample.automatic.sha256_pcm);
  assert.ok(sample.decisions.some(d => d.factor < 1));
  for (let i = 0; i < sample.decisions.length; i++) {
    const a = sample.baseline.timing.segments[i], b = sample.automatic.timing.segments[i];
    if (sample.decisions[i].factor < 1) assert.ok(b.speech_end - b.from > a.speech_end - a.from);
    assert.ok(Math.abs((a.until - a.speech_end) - (b.until - b.speech_end)) < 1e-8);
  }
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
    for (const name of ['baseline', 'automatic']) await expect(page.locator('#' + name + 'Play')).toBeEnabled();
    await expect(page.locator('#text')).toContainText(language === 'es' ? '¡Buenas, explorador!' : 'Hello, explorer!');
    await expect(page.locator('#text')).toContainText(language === 'es' ? '¡Hasta luego, explorador!' : 'See you later, explorer!');
    if (data.metrics) await expect(page.locator('#evaluation')).toContainText('no calidad visual');
    await page.locator('#baselinePlay').click();
    await expect.poll(() => page.locator('#baselineAudio').evaluate(a => a.currentTime)).toBeGreaterThan(.5);
    await page.locator('#automaticPlay').click();
    await expect.poll(() => page.locator('#baselineAudio').evaluate(a => a.paused)).toBe(true);
    await expect.poll(() => page.locator('#automaticAudio').evaluate(a => a.currentTime)).toBeGreaterThan(.7);
    assert.equal(await page.locator('#automaticAudio').evaluate(a => a.playbackRate), 1);
    await expect(page.locator('#automatic canvas')).toHaveAttribute('data-isa-speech-language', language);
    await page.locator('#automaticAudio').evaluate(a => { a.pause(); a.currentTime = 2.5; });
    await expect(page.locator('#automaticTime')).toContainText('2.500');
    await expect(page.locator('#automaticPhone')).toContainText('Fonema');
    await expect(page.locator('#automaticBars')).toBeVisible();
    assert.ok(await page.locator('#automaticBars').evaluate(canvas => {
      const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
      let colored = 0; for (let i = 3; i < pixels.length; i += 4) if (pixels[i]) colored++;
      return colored > 1000;
    }));
    const time = await page.locator('#automaticAudio').evaluate(a => a.currentTime);
    const src = await page.locator('#automaticAudio').getAttribute('src');
    if (data.models) {
      await page.locator('#model').selectOption('previous');
      assert.equal(await page.locator('#automaticAudio').evaluate(a => a.currentTime), time);
      await page.locator('#model').selectOption('balanced');
      assert.equal(await page.locator('#automaticAudio').getAttribute('src'), src);
    }
    if (language === 'en') {
      const signature = await page.locator('#automatic').getAttribute('data-plan-signature');
      await page.locator('#accelerate').uncheck();
      assert.notEqual(await page.locator('#automatic').getAttribute('data-plan-signature'), signature);
      await page.locator('#accelerate').check();
      assert.equal(await page.locator('#automaticAudio').evaluate(a => a.currentTime), time);
    }
    await page.screenshot({ path: path.join(folder, `automatic-${language}.png`), fullPage: true });
  }
  if (data.cases.length > 2) {
    for (const language of ['en', 'es']) {
      await page.locator('#language').selectOption(language);
      await expect(page.locator('#automaticPlay')).toBeEnabled();
      const options = await page.locator('#scenario option').evaluateAll(options => options.map(o => o.value));
      assert.ok(options.length >= 3);
      await page.locator('#scenario').selectOption(options.at(-1));
      await expect(page.locator('#automaticPlay')).toBeEnabled();
      await page.locator('#automaticPlay').click();
      await expect.poll(() => page.locator('#automaticAudio').evaluate(a => a.currentTime)).toBeGreaterThan(.5);
      await page.locator('#automaticAudio').evaluate(a => a.pause());
      await expect(page.locator('#automatic canvas')).toHaveAttribute('data-isa-speech-language', language);
      await page.screenshot({ path: path.join(folder, `novel-${language}.png`), fullPage: true });
    }
  }
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  await page.screenshot({ path: path.join(folder, 'automatic-mobile.png'), fullPage: true });
  assert.deepEqual(errors, []); assert.deepEqual(remote, []);
  console.log('Automatic rate ES/EN: genuine slower synthesis per selected phrase, pauses, narration, animation, exclusive audio, seeking, mobile, offline: OK');
} finally { await browser.close(); }
