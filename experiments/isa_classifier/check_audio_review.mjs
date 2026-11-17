import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import assert from 'node:assert/strict';

const frontend = path.resolve(process.argv[2]);
const output = path.resolve(process.argv[3]);
const { chromium, expect } = await import(pathToFileURL(path.join(frontend, 'node_modules/@playwright/test/index.mjs')));
const browser = await chromium.launch();
try {
  for (const language of ['es', 'en']) {
    const page = await browser.newPage({ viewport: { width: 1366, height: 900 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(pathToFileURL(path.join(output, `audio-review-${language}.html`)).href);
    const count = await page.locator('article').count();
    assert.ok(count > 1);
    await page.getByRole('button', { name: 'Exportar para entrenar', exact: true }).click();
    assert.match(await page.locator('#status').textContent(), /Faltan intervalos/);
    await page.getByRole('button', { name: 'Dividir', exact: true }).first().click();
    assert.equal(await page.locator('article').count(), count + 1);
    await page.getByRole('button', { name: 'Unir siguiente', exact: true }).first().click();
    assert.equal(await page.locator('article').count(), count);
    await page.locator('article select').first().selectOption('A');
    await page.getByRole('checkbox', { name: 'Revisado', exact: true }).first().check();
    let pending = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Guardar avance', exact: true }).click();
    let file = await pending;
    const progress = JSON.parse(await readFile(await file.path(), 'utf8'));
    assert.equal(progress.source, 'in-progress');
    assert.equal(progress.mouthCues[0].value, 'A');
    assert.equal(progress.mouthCues.filter(c => c.reviewed).length, 1);
    const picker = page.locator('#import');
    const invalid = { ...progress, sha256_pcm: 'wrong-recording' };
    await picker.setInputFiles({ name: 'wrong.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(invalid)) });
    await expect(page.locator('#status')).toContainText('otro audio');
    await page.getByRole('checkbox', { name: 'Revisado', exact: true }).first().uncheck();
    await picker.setInputFiles({ name: 'progress.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(progress)) });
    assert.equal(await page.getByRole('checkbox').filter({ visible: true }).count(), count);
    await expect(page.locator('input[type=checkbox]:checked')).toHaveCount(1);
    for (const checkbox of await page.getByRole('checkbox', { name: 'Revisado', exact: true }).all()) await checkbox.check();
    pending = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Exportar para entrenar', exact: true }).click();
    file = await pending;
    const complete = JSON.parse(await readFile(await file.path(), 'utf8'));
    assert.equal(complete.source, 'human-reviewed');
    assert.ok(complete.mouthCues.every(c => c.reviewed));
    assert.equal(complete.sha256_pcm, progress.sha256_pcm);
    // Synthetic QA labels are discarded, never added to training data.
    await page.screenshot({ path: path.join(output, `audio-review-${language}-desktop.png`) });
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    assert.deepEqual(errors, []);
    console.log(`${language}: boundary tools, progress, identity rejection, resume, complete export and mobile: OK`);
    await page.close();
  }
} finally {
  await browser.close();
}
