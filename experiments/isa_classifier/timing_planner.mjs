// Experimental only. No production imports this module.
export const FPS = 24;
export const defaults = Object.freeze({
  es: Object.freeze({ offsetMs: 0, openOffsetMs: 0, closeOffsetMs: 0, minimumRunMs: 125, maxDrift: 4, candidatePauses: false, minimumQuietMs: 90, avoidLongClosures: false }),
  en: Object.freeze({ offsetMs: 0, openOffsetMs: 0, closeOffsetMs: 0, minimumRunMs: 83, maxDrift: 6, candidatePauses: false, minimumQuietMs: 70, avoidLongClosures: true }),
});
const mapped = shape => ({ A: 'X', G: 'B', H: 'C' })[shape] ?? shape;

export function speechEvidence(timing, time) {
  if (!timing.envelope?.length || !Number.isFinite(timing.quiet_threshold)) return false;
  if (timing.inserted_pauses.some(p => p.start <= time && time < p.end)) return false;
  if (timing.quiet_candidates.some(p => p.duration_ms >= 150 && p.start <= time && time < p.end)) return false;
  const center = Math.floor(time / timing.duration * timing.envelope.length);
  const radius = Math.max(1, Math.ceil(.025 / timing.duration * timing.envelope.length));
  return timing.envelope.slice(Math.max(0, center - radius), center + radius + 1)
    .some(value => value > timing.quiet_threshold);
}

export function auditClosures(plan, timing, catalog, range) {
  const shapes = labelsFor(catalog), cycle = range.end - range.first, runs = [];
  let start = null;
  for (let i = 0; i <= plan.frames.length; i++) {
    const closed = i < plan.frames.length && shapes[range.first + (plan.frames[i] - range.first) % cycle] === 'X';
    if (closed && start === null) start = i;
    if (!closed && start !== null) {
      let mismatch = 0;
      for (let j = start; j < i; j++)
        if (plan.wanted[j] !== 'X' && speechEvidence(timing, (j + .5) / FPS)) mismatch++;
      if (mismatch >= 2) runs.push({ start: start / FPS, end: Math.min(i / FPS, timing.duration),
        durationMs: (i - start) / FPS * 1000, activeMismatchMs: mismatch / FPS * 1000,
        sourceFrames: plan.frames.slice(start, i), verified: false });
      start = null;
    }
  }
  return runs;
}

export function labelsFor(catalog) {
  return catalog.sourceFrames.map((_, index) => {
    const state = catalog.mouthStates?.[index];
    if (state !== undefined && !['open', 'closed', 'uncertain'].includes(state)) throw Error('Invalid reviewed mouth state');
    if (state === 'closed') return 'X';
    let nearest = 0;
    for (let i = 1; i < catalog.candidates.length; i++)
      if (Math.abs(index - catalog.candidates[i]) < Math.abs(index - catalog.candidates[nearest])) nearest = i;
    const label = mapped(catalog.labels[nearest]);
    // Visible aperture is known; the fine phonetic class may remain unknown.
    return state === 'open' && label === 'X' ? '?' : label;
  });
}

export function wantedAt(cues, timing, time, options) {
  const t = Math.max(0, Math.min(timing.duration - 1e-8, time + options.offsetMs / 1000));
  const raw = at => mapped(cues.find(c => c.start <= at && at < c.end)?.value ?? 'X');
  const intervals = [...cues.filter(c => mapped(c.value) === 'X'), ...timing.inserted_pauses,
    ...(options.candidatePauses ? timing.quiet_candidates.filter(p => p.duration_ms >= options.minimumQuietMs) : [])]
    .map(c => ({ start: c.start, end: c.end })).sort((a, b) => a.start - b.start);
  const merged = [];
  for (const interval of intervals) {
    const last = merged.at(-1);
    if (last && interval.start <= last.end + 1e-8) last.end = Math.max(last.end, interval.end);
    else merged.push(interval);
  }
  for (const interval of merged) {
    const start = Math.max(0, interval.start - (options.closeOffsetMs ?? 0) / 1000);
    // Never erase a short closure with conflicting timing adjustments.
    const end = Math.min(timing.duration, Math.max(start + Math.min(interval.end - interval.start, 1 / FPS),
      interval.end - (options.openOffsetMs ?? 0) / 1000));
    if (start <= t && t < end) return 'X';
  }
  for (const interval of merged) if (interval.start <= t && t < interval.end) {
    const delayedStart = interval.start - (options.closeOffsetMs ?? 0) / 1000;
    return t < delayedStart ? raw(Math.max(0, interval.start - 1e-7))
      : raw(Math.min(timing.duration - 1e-8, interval.end + 1e-7));
  }
  return raw(t);
}

export function planTiming(cues, timing, catalog, range, options) {
  if (catalog.reviewedLoop) {
    const loop = catalog.reviewedLoop;
    if (loop.first !== range.first || loop.end !== range.end
      || ![loop.face, loop.velocity, loop.maxFace, loop.maxVelocity].every(Number.isFinite)
      || loop.face < 0 || loop.velocity < 0 || loop.face > loop.maxFace || loop.velocity > loop.maxVelocity)
      throw Error('Unverified reviewed loop boundary');
  }
  if (!Number.isFinite(timing.duration) || timing.duration <= 0 || timing.duration > 90
      || !Number.isFinite(options.offsetMs) || Math.abs(options.offsetMs) > 250
      || !Number.isFinite(options.openOffsetMs ?? 0) || Math.abs(options.openOffsetMs ?? 0) > 150
      || !Number.isFinite(options.closeOffsetMs ?? 0) || Math.abs(options.closeOffsetMs ?? 0) > 150
      || !Number.isFinite(options.minimumQuietMs) || options.minimumQuietMs < 40 || options.minimumQuietMs > 300
      || !Number.isFinite(options.minimumRunMs) || options.minimumRunMs < 40 || options.minimumRunMs > 350
      || !Number.isInteger(options.maxDrift) || options.maxDrift < 0 || options.maxDrift > 12)
    throw Error('Invalid timing experiment parameters');
  const count = Math.ceil(timing.duration * FPS), cycle = range.end - range.first;
  const shapes = labelsFor(catalog), minimumRun = Math.max(1, Math.round(options.minimumRunMs / 1000 * FPS));
  const wanted = Array.from({ length: count }, (_, i) => wantedAt(cues, timing, (i + .5) / FPS, options));
  const active = Array.from({ length: count }, (_, i) => speechEvidence(timing, (i + .5) / FPS));
  const openingSoon = wanted.map((_, i) => [1, 2].some(ahead => wanted[i + ahead] !== undefined
    && wanted[i + ahead] !== 'X' && active[i + ahead]));
  const local = index => range.first + ((index - range.first) % cycle);
  const emission = (index, i) => shapes[local(index)] === wanted[i] ? 0
    : shapes[local(index)] === '?' && wanted[i] !== 'X' ? .5
    : wanted[i] === 'X' || ((options.avoidLongClosures || catalog.mouthStates?.[local(index)] === 'closed')
      && active[i] && shapes[local(index)] === 'X') ? 8 : 2;
  let states = new Map([[`${range.first}:${minimumRun}:0`, { index: range.first, run: minimumRun, streak: 0, cost: emission(range.first, 0), path: [range.first] }]]);
  for (let i = 1; i < count; i++) {
    const next = new Map();
    for (const state of states.values()) for (const step of [1, 0, 2, ...(options.avoidLongClosures ? [3, 4, 5] : [])]) {
      const index = state.index + step;
      if (Math.abs(index - range.first - i) > options.maxDrift) continue;
      // Holds do not cut between poses. Skips require the measured seam guard.
      const from = local(state.index), to = local(index);
      const compression = options.avoidLongClosures && active[i]
        && (wanted[i] !== 'X' || (openingSoon[i] && shapes[to] === 'X')) && step >= 2
        && to > from && shapes[from] === 'X'
        && Array.from({ length: step - 1 }, (_, j) => shapes[from + j + 1]).every(shape => shape === 'X');
      if (step > 2 && !compression) continue;
      if (step !== 1 && state.run < minimumRun && !compression) continue;
      const jump = step >= 2 ? catalog.jumps[String(from)]?.[step - 2] : null;
      if (step >= 2 && (to < from || !jump || jump.pose > .04 || jump.motion > .025)) continue;
      const run = step === 1 ? Math.min(minimumRun, state.run + 1) : 0;
      const mismatch = options.avoidLongClosures && active[i] && wanted[i] !== 'X' && shapes[to] === 'X';
      const streak = mismatch ? Math.min(6, state.streak + 1) : 0;
      const cost = state.cost + emission(index, i) + Math.abs(index - range.first - i) * .12
        + (step === 1 ? 0 : .8 + Math.max(0, step - 2) * .2)
        + (jump ? jump.pose * 30 + jump.motion * 40 : 0) + Math.max(0, streak - 2) * 3;
      const key = `${index}:${run}:${streak}`, previous = next.get(key);
      if (!previous || cost < previous.cost) next.set(key, { index, run, streak, cost, path: [...state.path, index] });
    }
    if (!next.size) throw Error('No continuous timing path');
    states = next;
  }
  const best = [...states.values()].reduce((a, b) => a.cost <= b.cost ? a : b);
  const frames = best.path;
  const deltas = frames.slice(1).map((value, i) => value - frames[i]);
  const slopes = frames.map((_, i) => {
    if (i === 0) return deltas[0] ?? 0;
    if (i === frames.length - 1) return deltas.at(-1) ?? 0;
    const a = deltas[i - 1], b = deltas[i];
    return a > 0 && b > 0 ? 2 * a * b / (a + b) : 0;
  });
  return { frames, wanted, sourceSecondsAt(time) {
    const t = Math.max(0, Math.min(timing.duration, Number.isFinite(time) ? time : 0));
    const position = Math.min(frames.length - 1, t * FPS), i = Math.floor(position), f = position - i;
    const next = frames[i + 1] ?? frames[i], a = slopes[i], b = slopes[i + 1] ?? 0;
    // Monotone Hermite interpolation changes playback speed smoothly. Source
    // images stay in their original bank; no fixed-time jump or accumulated lag.
    const source = (2 * f ** 3 - 3 * f ** 2 + 1) * frames[i]
      + (f ** 3 - 2 * f ** 2 + f) * a + (-2 * f ** 3 + 3 * f ** 2) * next
      + (f ** 3 - f ** 2) * b;
    return (source - range.first) / FPS;
  } };
}
