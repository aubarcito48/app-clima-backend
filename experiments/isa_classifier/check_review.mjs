// Browser smoke check using the frontend's existing Playwright installation.
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import assert from 'node:assert/strict';

const frontend = path.resolve(process.argv[2]);
const output = path.resolve(process.argv[3]);
const { chromium } = await import(pathToFileURL(path.join(frontend, 'node_modules/playwright/index.mjs')));
const browser = await chromium.launch();
try {
  for (const language of ['es', 'en']) {
    const page = await browser.newPage({ viewport: { width: 1366, height: 900 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(pathToFileURL(path.join(output, `review-${language}.html`)).href);
    assert.equal(await page.locator('article').count(), 204);
    assert.equal(await page.locator('select[data-mouth]:valid').count(), 0);
    await page.locator('select[data-mouth]').first().selectOption('X');
    await page.locator('select[data-attribute="eyes"]').first().selectOption('closed');
    const downloaded = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Descargar etiquetas revisadas' }).click();
    const download = await downloaded;
    const data = JSON.parse(await readFile(await download.path(), 'utf8'));
    assert.equal(data.language, language);
    assert.deepEqual(data.labels, [{ frame: 0, value: 'X', reviewed: true }]);
    assert.deepEqual(data.attributes, [{ frame: 0, attribute: 'eyes', value: 'closed', reviewed: true }]);
    // This is only an export test; never retain these synthetic choices as
    // human-reviewed training data.
    await page.screenshot({ path: path.join(output, `review-${language}-desktop.png`) });
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    assert.deepEqual(errors, []);
    console.log(`${language}: 204 frames, pending labels, export, mobile width: OK`);
    await page.close();
  }
} finally {
  await browser.close();
}
