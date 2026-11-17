// Bounded timing-policy calibration, not new human boundary labels.
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { defaults, planTiming, labelsFor, speechEvidence, FPS } from './timing_planner.mjs';

const frontend = path.resolve(process.argv[2]), folder = path.resolve(process.argv[3]);
const batch = JSON.parse(await readFile(path.join(folder, 'batch.json'), 'utf8'));
const range = JSON.parse(await readFile(path.join(frontend, 'src/app/shared/isabel/isa-speech-ranges.json'), 'utf8')).en;
const catalog = JSON.parse(await readFile(path.join(frontend, 'src/app/shared/isabel/isa-speech-selection-en.json'), 'utf8'));
const shapes = labelsFor(catalog), cycle = range.end - range.first;
const mapped = value => ({ A: 'X', G: 'B', H: 'C' })[value] ?? value;
const at = (cues, t) => cues.find(c => c.start <= t && t < c.end)?.value ?? 'X';

function evaluate(row, profile) {
  const plan = planTiming(row.cues, row.timing, catalog, range, profile);
  const counts = { openActive: 0, closedOnOpen: 0, pauses: 0, missedPauses: 0,
    protected: 0, missedProtected: 0, advice: 0, wrongShape: 0 };
  for (let i = 0; i < plan.frames.length; i++) {
    const time = Math.min(row.timing.duration - 1e-8, (i + .5) / FPS);
    const visual = shapes[range.first + (plan.frames[i] - range.first) % cycle];
    const pause = row.timing.inserted_pauses.some(p => p.start <= time && time < p.end);
    if (pause) { counts.pauses++; if (visual !== 'X') counts.missedPauses++; }
    // Preserve true bilabial requests rather than treating every closure as bad.
    if (at(row.cues, time) === 'A') { counts.protected++; if (visual !== 'X') counts.missedProtected++; }
    if (row.advice_spans.some(([a, b]) => a <= time && time < b)) {
      const target = mapped(at(row.reference, time));
      counts.advice++;
      if (visual !== target) counts.wrongShape++;
      if (target !== 'X' && speechEvidence(row.timing, time)) {
        counts.openActive++;
        if (visual === 'X') counts.closedOnOpen++;
      }
    }
    if (i) {
      const step = plan.frames[i] - plan.frames[i - 1];
      assert.ok(step >= 0 && step <= 5);
      assert.ok(Math.abs(plan.frames[i] - range.first - i) <= profile.maxDrift);
      if (step >= 2) {
        const from = range.first + (plan.frames[i - 1] - range.first) % cycle;
        const to = range.first + (plan.frames[i] - range.first) % cycle;
        const jump = catalog.jumps[String(from)]?.[step - 2];
        assert.ok(to > from && jump && jump.pose <= .04 && jump.motion <= .025);
      }
    }
  }
  return { id: row.id, ...counts };
}
function summarize(rows) {
  const sums = Object.fromEntries(Object.keys(rows[0]).filter(k => k !== 'id').map(k => [k, rows.reduce((s, r) => s + r[k], 0)]));
  const rate = (a, b) => sums[b] ? sums[a] / sums[b] : 0;
  const result = { recordings: rows.length, counts: sums, falseClosure: rate('closedOnOpen', 'openActive'),
    pauseMiss: rate('missedPauses', 'pauses'), protectedMiss: rate('missedProtected', 'protected'),
    mouthMismatch: rate('wrongShape', 'advice') };
  result.objective = result.falseClosure + 2 * result.pauseMiss + 2 * result.protectedMiss + .1 * result.mouthMismatch;
  return result;
}
const english = batch.rows.filter(r => r.language === 'en');
const splits = Object.fromEntries(['train', 'dev', 'test'].map(split => [split, english.filter(r => r.split === split)]));
assert.deepEqual(Object.fromEntries(Object.entries(splits).map(([k, v]) => [k, v.length])), { train: 40, dev: 8, test: 16 });
const baselineProfile = { ...defaults.en };
const candidates = [];
// Fixed grid. No global offsets or voice changes; only local frame timing.
for (const minimumRunMs of [83, 125]) for (const maxDrift of [4, 6, 8]) {
  const profile = { ...defaults.en, minimumRunMs, maxDrift };
  const train = summarize(splits.train.map(row => evaluate(row, profile)));
  candidates.push({ profile, train });
  console.log(JSON.stringify({ stage: 'train', minimumRunMs, maxDrift, objective: train.objective }));
}
const baseline = candidates.find(c => c.profile.minimumRunMs === 83 && c.profile.maxDrift === 6);
const eligible = candidates.filter(c => c.train.pauseMiss <= baseline.train.pauseMiss + 1e-9
  && c.train.protectedMiss <= baseline.train.protectedMiss + 1e-9);
const shortlist = [...new Set([baseline, ...eligible.sort((a, b) => a.train.objective - b.train.objective).slice(0, 3)])];
for (const candidate of shortlist) candidate.dev = summarize(splits.dev.map(row => evaluate(row, candidate.profile)));
const best = shortlist.filter(c => c.dev.pauseMiss <= baseline.dev.pauseMiss + 1e-9
  && c.dev.protectedMiss <= baseline.dev.protectedMiss + 1e-9)
  .sort((a, b) => a.dev.objective - b.dev.objective || a.train.objective - b.train.objective)[0];
// Freeze the profile before accessing test performance.
const policy = { version: 1, kind: 'bounded-local-timing-calibration', profiles: { es: { ...defaults.es }, en: best.profile },
  source_plan_sha256: batch.source_plan_sha256, human_reviewed: false,
  learned_on: { language: 'en', train: splits.train.map(r => r.sha256_pcm), dev: splits.dev.map(r => r.sha256_pcm) },
  warning: 'Weak acoustic/visual labels; not a trained verifier of natural phonetic boundaries. Spanish profile unchanged.' };
await writeFile(path.join(folder, 'policy.json'), JSON.stringify(policy, null, 2));
const results = splits.test.map(row => ({ id: row.id, baseline: evaluate(row, baselineProfile), calibrated: evaluate(row, best.profile) }));
const report = { selected: best.profile, default: baselineProfile, shortlist,
  test: { baseline: summarize(results.map(r => r.baseline)), calibrated: summarize(results.map(r => r.calibrated)), cases: results },
  warning: batch.warning, selection: '6 fixed profiles; training shortlist, dev selection with pause/closure safeguards; test evaluated once' };
await writeFile(path.join(folder, 'evaluation.json'), JSON.stringify(report, null, 2));
console.log(JSON.stringify({ selected: best.profile, test: { baseline: report.test.baseline, calibrated: report.test.calibrated } }));
