import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { defaults, planTiming, labelsFor, FPS } from './timing_planner.mjs';

const frontend = path.resolve(process.argv[2]), folder = path.resolve(process.argv[3]);
const data = JSON.parse(await readFile(path.join(folder, 'timing.json'), 'utf8'));
const ranges = JSON.parse(await readFile(path.join(frontend, 'src/app/shared/isabel/isa-speech-ranges.json'), 'utf8'));
const results = [];
for (const sample of data.cases) {
  const language = sample.language, timing = data.timing.find(r => r.language === language);
  const catalog = JSON.parse(await readFile(path.join(frontend, `src/app/shared/isabel/isa-speech-selection${language === 'en' ? '-en' : ''}.json`), 'utf8'));
  const shapes = labelsFor(catalog), range = ranges[language], cycle = range.end - range.first;
  const plan = planTiming(sample.versions.v6.cues, timing, catalog, range, defaults[language]);
  let holds = 0, skips = 0, closed = 0, misses = 0, maxDrift = 0;
  for (let i = 0; i < plan.frames.length; i++) {
    const frame = plan.frames[i], shape = shapes[range.first + (frame - range.first) % cycle];
    if (i && frame === plan.frames[i - 1]) holds++;
    if (i && frame === plan.frames[i - 1] + 2) skips++;
    maxDrift = Math.max(maxDrift, Math.abs(frame - range.first - i));
    if (plan.wanted[i] === 'X') { closed++; if (shape !== 'X') misses++; }
  }
  results.push({ language, sha256_pcm: sample.sha256_pcm, parameters: defaults[language], reviewed: false,
    advice_words_per_second: timing.advice_words_per_second, known_pauses: timing.inserted_pauses.length,
    candidate_gaps: timing.quiet_candidates.length, holds, skips, requested_closed_frame_instants: closed,
    unfulfilled_closed_frame_instants: misses, max_phase_displacement_ms: maxDrift / FPS * 1000,
    warning: 'provisional visual labels; diagnostic not accuracy; no word alignment' });
}
await writeFile(path.join(folder, 'timing-diagnostics.json'), JSON.stringify(results, null, 2));
console.log(JSON.stringify(results));
