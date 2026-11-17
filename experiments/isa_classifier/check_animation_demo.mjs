import assert from 'node:assert/strict';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { readFile } from 'node:fs/promises';

const frontend = path.resolve(process.argv[2]), folder = path.resolve(process.argv[3]);
const { chromium, expect } = await import(pathToFileURL(path.join(frontend, 'node_modules/@playwright/test/index.mjs')));
const data = JSON.parse(await readFile(path.join(folder, 'demo.json'), 'utf8'));
const versions = Object.keys(data.cases[0].versions);
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1366, height: 900 }, reducedMotion: 'no-preference' });
  const errors = [], remote = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => { if (/^https?:/.test(request.url())) remote.push(request.url()); });
  await page.goto(pathToFileURL(path.join(folder, 'index.html')).href);
  await expect(page.getByRole('button', { name: 'Reproducir desde el inicio', exact: true })).toBeEnabled();
  await expect(page.locator('canvas')).toHaveCount(2);
  for (const language of ['en', 'es']) {
    for (const model of versions) {
      await page.locator('#language').selectOption(language);
      await page.locator('#model').selectOption(model);
      await expect(page.getByRole('button', { name: 'Reproducir desde el inicio', exact: true })).toBeEnabled();
      await expect(page.locator('canvas').first()).toHaveAttribute('data-isa-speech-language', language);
      await page.getByRole('button', { name: 'Reproducir desde el inicio', exact: true }).click();
      await expect.poll(() => page.locator('audio').evaluate(audio => audio.currentTime)).toBeGreaterThan(1.2);
      await page.locator('audio').evaluate(audio => audio.pause());
      for (const host of ['reference', 'own']) {
        await expect(page.locator(`#${host} canvas`)).toHaveAttribute('data-isa-speaking', 'true');
        await expect.poll(() => page.locator(`#${host} canvas`).getAttribute('data-isa-speech-blend')).not.toBe('0.000');
      }
      assert.match(await page.locator('#text').textContent(), language === 'es' ? /campera/ : /jacket/);
      const sample = data.cases.find(c => c.language === language);
      if (sample.narration_profile === 'app-greeting-v1') {
        const text = await page.locator('#text').textContent();
        assert.ok(text.startsWith(language === 'es' ? '¡Buenas, explorador!\n' : 'Hello, explorer!\n'));
        assert.ok(text.endsWith(language === 'es' ? '\n¡Hasta luego, explorador!' : '\nSee you later, explorer!'));
      }
      assert.ok(Number(await page.locator('#own').getAttribute('data-source-time')) > 0);
      await page.screenshot({ path: path.join(folder, `animation-${language}-${model}.png`), fullPage: true });
      // Exercise paused seeking without a second audio clock.
      await page.locator('#seek').fill('2.5');
      await page.locator('#seek').dispatchEvent('input');
      await expect(page.locator('#time')).toContainText('2.500');
      await page.locator('#speed').selectOption('0.75');
      assert.equal(await page.locator('audio').evaluate(audio => audio.playbackRate), .75);
      await page.locator('#speed').selectOption('1');
    }
  }
  await page.getByRole('button', { name: 'Cambiar tema', exact: true }).click();
  await page.screenshot({ path: path.join(folder, 'animation-dark.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  await page.goto(pathToFileURL(path.join(folder, 'extra-frames.html')).href);
  await expect(page.locator('article')).toHaveCount(24);
  await page.screenshot({ path: path.join(folder, 'extra-frames-mobile.png') });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  await page.setViewportSize({ width: 1366, height: 900 });
  await page.screenshot({ path: path.join(folder, 'extra-frames-desktop.png') });
  assert.deepEqual(errors, []);
  assert.deepEqual(remote, []);
  console.log(`ES/EN × ${versions.join('/')}: audio, portraits, seeking, speed, themes, mobile, 24 candidates, offline: OK`);
} finally {
  await browser.close();
}
