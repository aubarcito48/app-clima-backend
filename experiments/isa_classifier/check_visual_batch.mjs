import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { defaults, planTiming, auditClosures, labelsFor, FPS } from './timing_planner.mjs';

const frontend = path.resolve(process.argv[2]), folder = path.resolve(process.argv[3]);
const rows = JSON.parse(await readFile(path.join(folder, 'visual-batch.json'), 'utf8'));
const ranges = JSON.parse(await readFile(path.join(frontend, 'src/app/shared/isabel/isa-speech-ranges.json'), 'utf8'));
const catalogs = {};
for (const language of ['es', 'en']) catalogs[language] = JSON.parse(await readFile(process.argv[4]
  ? path.join(path.resolve(process.argv[4]), `catalog-${language}.json`)
  : path.join(frontend, `src/app/shared/isabel/isa-speech-selection${language === 'en' ? '-en' : ''}.json`), 'utf8'));
const results = [];
for (const row of rows) {
  const range = ranges[row.language], catalog = catalogs[row.language], cycle = range.end - range.first;
  const versions = {};
  for (const [version, cues] of Object.entries(row.versions)) {
    const options = defaults[row.language];
    const before = planTiming(cues, row.timing, catalog, range, { ...options, avoidLongClosures: false });
    const after = planTiming(cues, row.timing, catalog, range, options);
    const priorAlerts = auditClosures(before, row.timing, catalog, range);
    const nextAlerts = auditClosures(after, row.timing, catalog, range);
    const shapes = labelsFor(catalog);
    let pauseInstants = 0, pauseClosedBefore = 0, pauseClosedAfter = 0;
    for (let i = 0; i < after.frames.length; i++) {
      const time = (i + .5) / FPS;
      if (row.timing.inserted_pauses.some(p => p.start <= time && time < p.end)) {
        pauseInstants++;
        if (shapes[range.first + (before.frames[i] - range.first) % cycle] === 'X') pauseClosedBefore++;
        if (shapes[range.first + (after.frames[i] - range.first) % cycle] === 'X') pauseClosedAfter++;
      }
    }
    let held = 0, longestHold = 0, jumpCount = 0;
    for (let i = 1; i < after.frames.length; i++) {
      const step = after.frames[i] - after.frames[i - 1];
      held = step === 0 ? held + 1 : 0;
      longestHold = Math.max(longestHold, held);
      if (step >= 2) jumpCount++;
      assert.ok(step >= 0 && step <= 5);
      assert.ok(Math.abs(after.frames[i] - range.first - i) <= options.maxDrift);
      if (step >= 2) {
        const from = range.first + (after.frames[i - 1] - range.first) % cycle;
        const to = range.first + (after.frames[i] - range.first) % cycle;
        const jump = catalog.jumps[String(from)]?.[step - 2];
        assert.ok(to > from && jump && jump.pose <= .04 && jump.motion <= .025);
      }
    }
    let previous = -1;
    for (let i = 0; i <= Math.ceil(row.timing.duration * 120); i++) {
      const source = after.sourceSecondsAt(Math.min(row.timing.duration, i / 120));
      assert.ok(source >= previous - 1e-8); previous = source;
    }
    versions[version] = {
      continuity_checks_passed: true, bounded_jump_count: jumpCount,
      longest_repeated_frame_ms: longestHold / FPS * 1000,
      flagged_runs_before: priorAlerts.length, flagged_runs_after: nextAlerts.length,
      active_mismatch_ms_before: priorAlerts.reduce((sum, r) => sum + r.activeMismatchMs, 0),
      active_mismatch_ms_after: nextAlerts.reduce((sum, r) => sum + r.activeMismatchMs, 0),
      verified_pause_instants: pauseInstants, pause_closed_before: pauseClosedBefore, pause_closed_after: pauseClosedAfter };
  }
  results.push({ id: row.id, language: row.language, versions });
}
const report = { warning: 'provisional visual labels and activity heuristic, not accuracy; Spanish acceleration remains off', cases: results, summary: {} };
for (const language of ['es', 'en']) for (const version of Object.keys(rows[0].versions)) {
  const subset = results.filter(r => r.language === language).map(r => r.versions[version]);
  report.summary[`${language}-${version}`] = { recordings: subset.length,
    reduced_visual_mismatch: subset.filter(r => r.active_mismatch_ms_after < r.active_mismatch_ms_before).length,
    increased_visual_mismatch: subset.filter(r => r.active_mismatch_ms_after > r.active_mismatch_ms_before).length,
    before_ms: subset.reduce((sum, r) => sum + r.active_mismatch_ms_before, 0),
    after_ms: subset.reduce((sum, r) => sum + r.active_mismatch_ms_after, 0) };
  const summary = report.summary[`${language}-${version}`];
  summary.verified_pause_instants = subset.reduce((sum, r) => sum + r.verified_pause_instants, 0);
  summary.pause_closed_after = subset.reduce((sum, r) => sum + r.pause_closed_after, 0);
  summary.pause_closed_rate_after = summary.verified_pause_instants ? summary.pause_closed_after / summary.verified_pause_instants : null;
  summary.bounded_jump_count = subset.reduce((sum, r) => sum + r.bounded_jump_count, 0);
  summary.longest_repeated_frame_ms = Math.max(...subset.map(r => r.longest_repeated_frame_ms));
}
await writeFile(path.join(folder, 'visual-evaluation.json'), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report.summary));
