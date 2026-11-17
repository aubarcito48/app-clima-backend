import assert from 'node:assert/strict';
import { defaults, wantedAt, planTiming } from './timing_planner.mjs';

const cues = [{ start: 0, end: .2, value: 'B' }, { start: .2, end: .3, value: 'A' },
  { start: .3, end: .6, value: 'C' }, { start: .6, end: .7, value: 'X' }, { start: .7, end: 1, value: 'B' }];
const timing = { duration: 1, inserted_pauses: [], quiet_candidates: [{ start: .4, end: .5, duration_ms: 100 }] };
assert.equal(wantedAt(cues, timing, .22, defaults.en), 'X');
assert.equal(wantedAt(cues, timing, .17, { ...defaults.en, closeOffsetMs: 50 }), 'X');
assert.equal(wantedAt(cues, timing, .22, { ...defaults.en, closeOffsetMs: -50 }), 'B');
assert.equal(wantedAt(cues, timing, .27, { ...defaults.en, openOffsetMs: 50 }), 'C');
assert.equal(wantedAt(cues, timing, .32, { ...defaults.en, openOffsetMs: -50 }), 'X');
assert.equal(wantedAt(cues, timing, .45, defaults.en), 'C');
assert.equal(wantedAt(cues, timing, .45, { ...defaults.en, candidatePauses: true }), 'X');
const catalog = { sourceFrames: Array.from({ length: 30 }, (_, i) => i),
  candidates: Array.from({ length: 30 }, (_, i) => i), labels: Array.from({ length: 30 }, (_, i) => i % 6 < 2 ? 'X' : 'C'),
  jumps: Object.fromEntries(Array.from({ length: 30 }, (_, i) => [String(i), [{ pose: .01, motion: .01 }]])) };
const range = { first: 0, end: 30 };
const plan = planTiming(cues, timing, catalog, range, defaults.en);
assert.equal(plan.frames.length, 24);
for (let i = 1; i < plan.frames.length; i++) {
  assert.ok(plan.frames[i] - plan.frames[i - 1] >= 0);
  assert.ok(plan.frames[i] - plan.frames[i - 1] <= 2);
  assert.ok(Math.abs(plan.frames[i] - i) <= defaults.en.maxDrift);
}
const expected = plan.sourceSecondsAt(.7);
for (const t of [.9, 0, .2, .95, .7]) plan.sourceSecondsAt(t);
assert.equal(plan.sourceSecondsAt(.7), expected, 'seeking must not accumulate lag');
const blocked = structuredClone(catalog);
for (const rows of Object.values(blocked.jumps)) rows[0].pose = .5;
const safe = planTiming(cues, timing, blocked, range, defaults.en);
assert.ok(safe.frames.every((value, i) => i === 0 || value - safe.frames[i - 1] <= 1));
assert.throws(() => planTiming(cues, timing, catalog, range, { ...defaults.en, offsetMs: NaN }));
assert.throws(() => planTiming(cues, timing, catalog, range, { ...defaults.en, openOffsetMs: 200 }));
assert.throws(() => planTiming(cues, timing, catalog, range, { ...defaults.en, minimumQuietMs: -1 }));
assert.notEqual(defaults.es, defaults.en);
console.log('Timing planner: independent opening/closing, uncertain pauses opt-in, bounded forward motion, safe seams, stateless clock: OK');
