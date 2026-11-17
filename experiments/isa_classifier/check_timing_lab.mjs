import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const frontend = path.resolve(process.argv[2]), folder = path.resolve(process.argv[3]);
const { chromium, expect } = await import(pathToFileURL(path.join(frontend, 'node_modules/@playwright/test/index.mjs')));
const timingData = JSON.parse(await readFile(path.join(folder, 'timing.json'), 'utf8'));
const originalV6Case = Object.keys(timingData.cases[0].versions)[0] === 'v6';
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1366, height: 1000 }, reducedMotion: 'no-preference' });
  const errors = [], requests = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('request', r => { if (/^https?:/.test(r.url())) requests.push(r.url()); });
  await page.goto(pathToFileURL(path.join(folder, 'index.html')).href);
  await expect(page.locator('#play')).toBeEnabled();
  await expect(page.locator('#avoidLongClosures')).toBeChecked();
  const compressed = await page.locator('#own').getAttribute('data-plan-signature');
  await page.locator('#avoidLongClosures').uncheck(); await page.locator('#apply').click();
  assert.notEqual(await page.locator('#own').getAttribute('data-plan-signature'), compressed);
  await page.locator('#avoidLongClosures').check(); await page.locator('#apply').click();
  if (originalV6Case) {
    await expect(page.locator('#closureAlerts')).toContainText('167 ms');
    await page.getByRole('button', { name: 'Escuchar tramo 5.29 s', exact: true }).click();
    await expect.poll(() => page.locator('audio').evaluate(a => a.currentTime)).toBeGreaterThan(5.1);
    await expect.poll(() => page.locator('audio').evaluate(a => a.paused)).toBe(true);
    assert.ok(await page.locator('audio').evaluate(a => a.currentTime < 6.2));
  }
  for (const language of ['en', 'es']) {
    await page.locator('#language').selectOption(language);
    await expect(page.locator('#play')).toBeEnabled();
    await expect(page.locator('#own canvas')).toHaveAttribute('data-isa-speech-language', language);
    await expect(page.locator('#text')).toContainText(language === 'es' ? '¡Buenas, explorador!' : 'Hello, explorer!');
    await expect(page.locator('#text')).toContainText(language === 'es' ? '¡Hasta luego, explorador!' : 'See you later, explorer!');
    await expect(page.locator('#candidatePauses')).not.toBeChecked();
    await page.locator('#play').click();
    await expect.poll(() => page.locator('audio').evaluate(a => a.currentTime)).toBeGreaterThan(.7);
    await page.locator('audio').evaluate(a => a.pause());
    const position = await page.locator('audio').evaluate(a => a.currentTime);
    if (timingData.integrated) {
      await page.locator('#referenceSource').selectOption('v7-timed');
      await page.locator('#timingModel').selectOption('v7');
      assert.equal(await page.locator('#own').getAttribute('data-plan-signature'),
        await page.locator('#reference').getAttribute('data-plan-signature'));
      await page.locator('#timingModel').selectOption('v8');
      assert.notEqual(await page.locator('#own').getAttribute('data-plan-signature'),
        await page.locator('#reference').getAttribute('data-plan-signature'));
      assert.equal(await page.locator('audio').evaluate(a => a.currentTime), position);
      await expect(page.locator('#ownTitle')).toContainText('Fonemas Piper + tiempos');
      if (timingData.cases.find(c => c.language === language).versions.v9) {
        await page.locator('#timingModel').selectOption('v9');
        await expect(page.locator('#ownTitle')).toContainText('Híbrido entrenado + tiempos');
        await expect(page.locator('#own')).toHaveAttribute('data-model-version', 'v9');
        assert.equal(await page.locator('audio').evaluate(a => a.currentTime), position);
      }
    }
    const signature = await page.locator('#own').getAttribute('data-plan-signature');
    await page.locator('#offsetMs').fill(language === 'en' ? '100' : '-50');
    await page.locator('#openOffsetMs').fill('40');
    await page.locator('#closeOffsetMs').fill('-20');
    await page.locator('#apply').click();
    await expect(page.locator('#status')).toContainText('sin reiniciar');
    assert.equal(await page.locator('audio').evaluate(a => a.currentTime), position);
    assert.notEqual(await page.locator('#own').getAttribute('data-plan-signature'), signature);
    await page.locator('#candidatePauses').check();
    await page.locator('#apply').click();
    await page.locator('#referenceSource').selectOption('rhubarb');
    await page.locator('#seek').fill('2.5'); await page.locator('#seek').dispatchEvent('input');
    await expect(page.locator('#position')).toContainText('2.500');
    const phoneticCase = timingData.cases.find(c => c.language === language);
    if (phoneticCase.phonemes) {
      const phone = phoneticCase.phonemes.find(row => row.start <= 2.5 && 2.5 < row.end);
      await expect(page.locator('#position')).toContainText(phone ? `fonema /${phone.phoneme}/` : 'pausa insertada');
    }
    await page.screenshot({ path: path.join(folder, `timing-${language}-desktop.png`), fullPage: true });
  }
  await page.locator('#language').selectOption('en');
  await expect(page.locator('#play')).toBeEnabled();
  await expect(page.locator('#offsetMs')).toHaveValue('100');
  const validSignature = await page.locator('#own').getAttribute('data-plan-signature');
  await page.locator('#offsetMs').fill('999'); await page.locator('#apply').click();
  await expect(page.locator('#status')).toContainText('Invalid timing');
  assert.equal(await page.locator('#own').getAttribute('data-plan-signature'), validSignature);
  const pending = page.waitForEvent('download');
  await page.locator('#export').click();
  const downloaded = await pending;
  const report = JSON.parse(await readFile(await downloaded.path(), 'utf8'));
  assert.equal(report.profiles.en.offsetMs, 100); assert.equal(report.profiles.es.offsetMs, -50);
  assert.equal(report.reviewed, false);
  await page.locator('#reset').click();
  await expect(page.locator('#offsetMs')).toHaveValue('0');
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  await page.screenshot({ path: path.join(folder, 'timing-mobile.png'), fullPage: true });
  assert.deepEqual(errors, []); assert.deepEqual(requests, []);
  console.log('Timing lab ES/EN: audio, independent controls, no restart on apply, profile isolation/export, candidate toggle, seeking, mobile, offline: OK');
} finally { await browser.close(); }
