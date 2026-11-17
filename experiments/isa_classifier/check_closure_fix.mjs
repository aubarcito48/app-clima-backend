import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { defaults, planTiming, auditClosures, labelsFor, speechEvidence, FPS } from './timing_planner.mjs';

const frontend = path.resolve(process.argv[2]), folder = path.resolve(process.argv[3]);
const data = JSON.parse(await readFile(path.join(folder, 'timing.json'), 'utf8'));
const sample = data.cases.find(c => c.language === 'en'), timing = data.timing.find(c => c.language === 'en');
const catalog = JSON.parse(await readFile(path.join(frontend, 'src/app/shared/isabel/isa-speech-selection-en.json'), 'utf8'));
const range = { first: 12, end: 180 }, cycle = range.end - range.first, labels = labelsFor(catalog);
const old = planTiming(sample.versions.v6.cues, timing, catalog, range, { ...defaults.en, avoidLongClosures: false });
const next = planTiming(sample.versions.v6.cues, timing, catalog, range, defaults.en);
const before = auditClosures(old, timing, catalog, range).find(r => r.start <= 5.55 && r.end > 5.55);
const after = auditClosures(next, timing, catalog, range).find(r => r.start <= 5.55 && r.end > 5.55);
assert.ok(before && after);
assert.ok(after.durationMs < before.durationMs - 2 / FPS * 1000);
assert.ok(after.activeMismatchMs < before.activeMismatchMs);
for (let i = 1; i < next.frames.length; i++) {
  const step = next.frames[i] - next.frames[i - 1];
  assert.ok(step >= 0 && step <= 5);
  if (step >= 2) {
    const from = range.first + (next.frames[i - 1] - range.first) % cycle;
    const to = range.first + (next.frames[i] - range.first) % cycle;
    const jump = catalog.jumps[String(from)][step - 2];
    assert.ok(to > from && jump.pose <= .04 && jump.motion <= .025);
    if (step > 2) {
      assert.ok(speechEvidence(timing, (i + .5) / FPS));
      for (let source = from; source < to; source++) assert.equal(labels[source], 'X');
    }
  }
}
let previous = -1;
for (let i = 0; i <= Math.ceil(timing.duration * 240); i++) {
  const source = next.sourceSecondsAt(Math.min(timing.duration, i / 240));
  assert.ok(source >= previous - 1e-9, 'smooth speed must never rewind');
  previous = source;
}
const saved = next.sourceSecondsAt(5.55);
for (const t of [8, 1, 6, 0, 5.55]) next.sourceSecondsAt(t);
assert.equal(next.sourceSecondsAt(5.55), saved);
const report = { language: 'en', audio_sha256: sample.sha256_pcm, reviewed: false,
  before, after, method: 'local source-playback acceleration; monotone interpolation; original image bank unchanged' };
await writeFile(path.join(folder, 'closure-fix.json'), JSON.stringify(report, null, 2));
console.log(JSON.stringify({ before_ms: before.durationMs, after_ms: after.durationMs,
  before_source_frames: before.sourceFrames.length, after_sampled_instants: after.sourceFrames.length,
  pose_guards: 'pass', monotone_clock: 'pass' }));
