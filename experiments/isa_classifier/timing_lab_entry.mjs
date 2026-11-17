import { createIsaPortrait } from 'isa/portrait';
import { createIsaPlayback } from 'isa/playback';
import data from 'isa/timing-data';
import { defaults, planTiming, labelsFor, auditClosures, FPS } from './timing_planner.mjs';

const $ = id => document.getElementById(id), audio = $('audio');
const profiles = structuredClone(defaults);
let modelVersion = data.rightVersion ?? Object.keys(data.cases[0].versions)[0];
if (data.integrated) {
  for (const version of Object.keys(data.cases[0].versions)) {
    const option = document.createElement('option');
    option.value = version;
    option.textContent = version === 'v9' ? 'Híbrido entrenado + tiempos'
      : version === 'v8' ? 'Fonemas Piper + tiempos' : `${version.toUpperCase()} + tiempos`;
    $('timingModel').append(option);
  }
  $('timingModel').value = modelVersion;
  $('timingModel').onchange = () => { modelVersion = $('timingModel').value; apply(); };
}
const keys = ['offsetMs', 'openOffsetMs', 'closeOffsetMs', 'minimumRunMs', 'minimumQuietMs'];
const decode = src => Uint8Array.from(atob(src.split(',')[1]), c => c.charCodeAt(0)).buffer;
let sample, timing, reference, plan, catalog, range, shapes, ready = false, raf, generation = 0;
let reviewEnd = null;
const controllers = [];
const colors = { X: '#dde6eb', B: '#a8daf0', C: '#93d3b1', D: '#f5d17c', E: '#ebadc4', F: '#bfaaea' };

function readControls() {
  const profile = structuredClone(profiles[sample.language]);
  for (const key of keys) profile[key] = Number($(key).value);
  profile.candidatePauses = $('candidatePauses').checked;
  profile.avoidLongClosures = $('avoidLongClosures').checked;
  return profile;
}
function writeControls() {
  const profile = profiles[sample.language];
  for (const key of keys) $(key).value = profile[key];
  $('candidatePauses').checked = profile.candidatePauses;
  $('avoidLongClosures').checked = profile.avoidLongClosures;
}
function stopClock() { if (raf !== undefined) cancelAnimationFrame(raf); raf = undefined; }
function shapeAt(source) {
  const cycle = range.end - range.first;
  return shapes[range.first + Math.floor(Math.max(0, source) * FPS) % cycle];
}
function paint(time) {
  const canvas = $('timeline'), ctx = canvas.getContext('2d'), width = canvas.width;
  ctx.clearRect(0, 0, width, 240);
  const envelope = timing.envelope, max = Math.max(...envelope, 1e-6);
  ctx.strokeStyle = '#657e8d'; ctx.beginPath();
  envelope.forEach((value, i) => { const x = i / envelope.length * width; ctx.moveTo(x, 25 - value / max * 20); ctx.lineTo(x, 25 + value / max * 20); });
  ctx.stroke();
  for (const [rows, y, color] of [[timing.inserted_pauses, 60, '#3ca778'], [timing.quiet_candidates, 90, '#dfb148']]) {
    ctx.fillStyle = color;
    for (const row of rows) ctx.fillRect(row.start / sample.duration * width, y, (row.end - row.start) / sample.duration * width, 16);
  }
  for (let i = 0; i < plan.frames.length; i++) {
    const t = i / FPS, x = t / sample.duration * width, w = width / (sample.duration * FPS) + 1;
    const wanted = plan.wanted[i], chosen = shapeAt(plan.sourceSecondsAt(t)), old = shapeAt(reference.sourceSecondsAt(t));
    for (const [shape, y] of [[wanted, 125], [chosen, 160], [old, 195]]) {
      ctx.fillStyle = colors[shape] ?? '#ddd'; ctx.fillRect(x, y, w, 24);
      if (i === 0 || (y === 125 && wanted !== plan.wanted[i - 1])) {
        ctx.fillStyle = '#123952'; ctx.font = '12px system-ui'; ctx.fillText(shape ?? '?', x + 1, y + 17);
      }
    }
  }
  ctx.strokeStyle = '#b84528'; ctx.beginPath(); ctx.moveTo(time / sample.duration * width, 0); ctx.lineTo(time / sample.duration * width, 240); ctx.stroke();
}
function update() {
  if (!ready) return;
  const t = Math.max(0, Math.min(sample.duration, audio.currentTime));
  const before = reference.sourceSecondsAt(t), after = plan.sourceSecondsAt(t);
  controllers[0].setSpeechTime(before); controllers[1].setSpeechTime(after);
  $('reference').dataset.sourceTime = before; $('own').dataset.sourceTime = after;
  $('own').dataset.audioTime = t;
  $('seek').value = t;
  $('position').textContent = `${t.toFixed(3)} / ${sample.duration.toFixed(3)} s · control ${shapeAt(before)} · ensayo ${shapeAt(after)}`;
  if (sample.phonemes) {
    const phone = sample.phonemes.find(row => row.start <= t && t < row.end);
    $('position').textContent += phone
      ? ` · fonema /${phone.phoneme}/ → ${phone.shape}${phone.internal_boundary ? ' (transición estimada)' : ''}`
      : ' · pausa insertada';
  }
  paint(t);
}
function tick() {
  if (reviewEnd !== null && audio.currentTime >= reviewEnd) { audio.pause(); reviewEnd = null; }
  update(); if (!audio.paused && !audio.ended) raf = requestAnimationFrame(tick);
}
function recompute() {
  const profile = readControls();
  const raw = $('referenceSource').value === 'rhubarb' ? sample.audio : sample.versions[modelVersion].audio;
  const nextReference = $('referenceSource').value === 'v7-timed'
    ? planTiming(sample.versions.v7.cues, timing, catalog, range, profile)
    : createIsaPlayback(decode(raw), sample.language);
  if (!nextReference) throw Error('Invalid reference audio');
  const nextPlan = planTiming(sample.versions[modelVersion].cues, timing, catalog, range, profile);
  reference = nextReference; plan = nextPlan; profiles[sample.language] = profile;
  if (data.integrated) {
    $('referenceTitle').textContent = $('referenceSource').selectedOptions[0].textContent;
    $('ownTitle').textContent = $('timingModel').selectedOptions[0].textContent;
    $('reference').dataset.planSignature = nextReference.frames?.join(',') ?? 'current-selector';
    $('own').dataset.modelVersion = modelVersion;
  }
  const beforePlan = planTiming(sample.versions[modelVersion].cues, timing, catalog, range, { ...profile, avoidLongClosures: false });
  const beforeAlerts = auditClosures(beforePlan, timing, catalog, range), afterAlerts = auditClosures(plan, timing, catalog, range);
  $('closureAlerts').replaceChildren();
  for (const alert of beforeAlerts) {
    const after = afterAlerts.find(row => row.start < alert.end && row.end > alert.start);
    const row = document.createElement('tr');
    const beforeCell = document.createElement('td'), afterCell = document.createElement('td'), action = document.createElement('td');
    beforeCell.textContent = `${alert.start.toFixed(3)}–${alert.end.toFixed(3)} s · ${Math.round(alert.durationMs)} ms`;
    afterCell.textContent = after ? `${after.start.toFixed(3)}–${after.end.toFixed(3)} s · ${Math.round(after.durationMs)} ms` : 'Sin cierre prolongado detectado';
    const button = document.createElement('button'); button.textContent = `Escuchar tramo ${alert.start.toFixed(2)} s`;
    button.onclick = async () => { audio.currentTime = Math.max(0, alert.start - .2); reviewEnd = Math.min(sample.duration, alert.end + .3); await audio.play(); };
    action.append(button); row.append(beforeCell, afterCell, action); $('closureAlerts').append(row);
  }
  let different = 0, holds = 0, skips = 0, closedWanted = 0, closedMissing = 0;
  for (let i = 0; i < plan.frames.length; i++) {
    const t = i / FPS;
    if (Math.floor(reference.sourceSecondsAt(t) * FPS) !== Math.floor(plan.sourceSecondsAt(t) * FPS)) different++;
    if (i && plan.frames[i] === plan.frames[i - 1]) holds++;
    if (i && plan.frames[i] === plan.frames[i - 1] + 2) skips++;
    if (plan.wanted[i] === 'X') { closedWanted++; if (shapeAt(plan.sourceSecondsAt(t)) !== 'X') closedMissing++; }
  }
  const accelerated = plan.frames.filter((f, i) => i > 0 && f - plan.frames[i - 1] > 1).length;
  $('planInfo').textContent = `Ajustes: ${holds} retenciones breves y ${accelerated} intervalos de avance acelerado; ${different} instantes diferentes del control. `
    + `Boca cerrada solicitada: ${closedWanted}; sin cierre disponible/elegido: ${closedMissing}. Son etiquetas provisionales, no precisión validada.`;
  $('own').dataset.planSignature = plan.frames.join(',');
  update();
}
async function changeLanguage() {
  const token = ++generation; ready = false; stopClock(); audio.pause(); $('play').disabled = true;
  reviewEnd = null;
  sample = data.cases.find(c => c.language === $('language').value);
  timing = data.timing.find(c => c.language === sample.language);
  catalog = data.catalogs[sample.language]; range = data.ranges[sample.language]; shapes = labelsFor(catalog);
  $('text').textContent = sample.text;
  $('measurements').textContent = `Ritmo medio del consejo en esta muestra: ${timing.advice_words_per_second.toFixed(2)} palabras/s. `
    + `${timing.inserted_pauses.length} pausas insertadas conocidas; ${timing.quiet_candidates.length} intervalos de energía baja por revisar.`;
  $('segments').replaceChildren();
  for (const segment of timing.segments) {
    const row = document.createElement('tr');
    for (const text of [segment.text, `${segment.from.toFixed(3)} / ${segment.speech_end.toFixed(3)} s`,
      `${Math.round((segment.until - segment.speech_end) * 1000)} ms`, segment.words_per_second.toFixed(2)]) {
      const cell = document.createElement('td'); cell.textContent = text; row.append(cell);
    }
    $('segments').append(row);
  }
  writeControls(); recompute();
  controllers.forEach(c => { c.setSpeaking(false); c.setSpeechLanguage(sample.language); c.setWorking(true); });
  const loaded = new Promise((resolve, reject) => { audio.addEventListener('loadedmetadata', resolve, { once: true }); audio.addEventListener('error', () => reject(Error('Audio unavailable')), { once: true }); });
  audio.src = sample.audio; audio.load(); await loaded;
  if (generation !== token) return;
  $('seek').max = sample.duration; ready = true; $('play').disabled = false; update(); $('status').textContent = 'Listo para escuchar y ajustar.';
}
audio.addEventListener('play', () => { controllers.forEach(c => { c.setWorking(false); c.setSpeaking(true); }); stopClock(); tick(); });
audio.addEventListener('pause', () => { stopClock(); update(); });
audio.addEventListener('seeked', update); audio.addEventListener('timeupdate', update);
audio.addEventListener('ended', () => { stopClock(); controllers.forEach(c => c.setSpeaking(false)); });
$('play').onclick = async () => { reviewEnd = null; audio.currentTime = 0; try { await audio.play(); } catch (error) { $('status').textContent = error.message; } };
$('seek').oninput = () => { if (!ready) return; audio.pause(); audio.currentTime = Number($('seek').value); controllers.forEach(c => { c.setWorking(false); c.setSpeaking(true); }); update(); };
$('speed').onchange = () => { audio.playbackRate = Number($('speed').value); };
$('language').onchange = () => changeLanguage().catch(error => { $('status').textContent = error.message; });
function apply() { try { recompute(); $('status').textContent = 'Perfil aplicado al mismo instante del audio; sin reiniciar ni acumular retraso.'; } catch (error) { $('status').textContent = error.message; } }
$('apply').onclick = apply; $('referenceSource').onchange = apply;
$('reset').onclick = () => { profiles[sample.language] = structuredClone(defaults[sample.language]); writeControls(); apply(); };
$('export').onclick = () => {
  const report = { version: 1, model: modelVersion, experimental: true, reviewed: false, profiles,
    audio: data.timing.map(c => ({ language: c.language, sha256_pcm: c.sha256_pcm })) };
  const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }));
  const a = document.createElement('a'); a.href = url; a.download = 'isa-timing-profiles.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
};
window.addEventListener('pagehide', () => { audio.pause(); stopClock(); controllers.forEach(c => c.destroy()); }, { once: true });
async function init() {
  try { for (const id of ['reference', 'own']) { const c = await createIsaPortrait($(id)); c.play('isa-awake'); controllers.push(c); } await changeLanguage(); }
  catch (error) { $('status').textContent = error.message; }
}
init();
