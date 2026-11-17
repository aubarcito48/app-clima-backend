import { createIsaPortrait } from 'isa/portrait';
import data from 'isa/timing-data';
import { defaults, planTiming, labelsFor, FPS } from './timing_planner.mjs';
const $ = id => document.getElementById(id), names = ['baseline', 'automatic'];
const controllers = {}, plans = {};
const model = $('model');
let failingImages = false;
if(data.functionalityReview){
  const decode=Image.prototype.decode;
  Image.prototype.decode=function(){return failingImages ? Promise.reject(new Error('Fallo temporal local')) : decode.call(this);};
}
if (model) for (const [key, label] of Object.entries(data.models ?? { previous: 'Híbrido anterior' })) {
  const option = document.createElement('option'); option.value = key; option.textContent = label; model.append(option);
}
function cuesFor(variant, key) { return variant.model_cues?.[key ?? variant.forcedModel ?? model?.value] ?? variant.cues; }
function audioFor(name) { return $((data.compareModels ? 'automatic' : name) + 'Audio'); }
function visualFor(name) {
  const visual = data.visualPolicies?.[name] ?? { catalogs: data.catalogs, ranges: data.ranges };
  if (data.visualPolicies && name === 'automatic' && $('visualMode')?.value === 'labels') {
    const catalogs = Object.fromEntries(Object.entries(visual.catalogs).map(([language, catalog]) => {
      const copy = { ...catalog }; delete copy.reviewedLoop; return [language, copy];
    }));
    return { catalogs, ranges: data.visualPolicies.baseline.ranges };
  }
  return visual;
}
function refresh(name) { for (const target of data.compareModels ? names : [name]) update(target); }
function recompute() {
  if (!sample || !controllers.baseline || !controllers.automatic) return;
  for (const name of names) {
    const variant = sample[name];
    const visual = visualFor(name);
    plans[name] = planTiming(cuesFor(variant), variant.timing, visual.catalogs[sample.language], visual.ranges[sample.language],
      { ...defaults[sample.language], avoidLongClosures: $('accelerate')?.checked ?? defaults[sample.language].avoidLongClosures });
    $(name).dataset.planSignature = plans[name].frames.join(',');
    update(name);
  }
}
function paint(name, t) {
  const canvas = $(name + 'Bars'); if (!canvas) return;
  const ctx = canvas.getContext('2d'), v = sample[name], width = canvas.width, height = canvas.height;
  const timing = v.timing, peak = Math.max(...timing.envelope, 1e-6);
  ctx.clearRect(0, 0, width, height); ctx.strokeStyle = '#657e8d'; ctx.beginPath();
  timing.envelope.forEach((energy, i) => { const x = i / timing.envelope.length * width;
    ctx.moveTo(x, 25 - energy / peak * 20); ctx.lineTo(x, 25 + energy / peak * 20); }); ctx.stroke();
  for (const [rows, y, color] of [[timing.inserted_pauses, 53, '#3ca778'], [timing.quiet_candidates, 76, '#dfb148']]) {
    ctx.fillStyle = color; for (const row of rows) ctx.fillRect(row.start / v.duration * width, y, (row.end - row.start) / v.duration * width, 14);
  }
  const colors = { X: '#dde6eb', A: '#dde6eb', B: '#a8daf0', C: '#93d3b1', D: '#f5d17c', E: '#ebadc4', F: '#bfaaea', G: '#a8daf0', H: '#93d3b1', '?': '#f2cc8f' };
  const visual = visualFor(name);
  const shapes = labelsFor(visual.catalogs[sample.language]), range = visual.ranges[sample.language], cycle = range.end - range.first;
  const shapeAt = plan => time => shapes[range.first + Math.floor(plan.sourceSecondsAt(time) * FPS) % cycle];
  const prior = plans[name + 'Prior'];
  const oldVisual = visualFor('baseline'), oldRange = oldVisual.ranges[sample.language];
  const oldShapes = labelsFor(oldVisual.catalogs[sample.language]), oldCycle = oldRange.end - oldRange.first;
  const priorAt = time => oldShapes[oldRange.first + Math.floor(prior.sourceSecondsAt(time) * FPS) % oldCycle];
  for (let i = 0; i < plans[name].frames.length; i++) {
    const time = i / FPS, x = time / v.duration * width, w = width / v.duration / FPS + 1;
    const desired = cuesFor(v).find(c => c.start <= time && time < c.end)?.value ?? 'X';
    for (const [shape, y] of [[desired, 101], [shapeAt(plans[name])(time), 126], [priorAt(time), 151]]) {
      ctx.fillStyle = colors[shape] ?? '#ddd'; ctx.fillRect(x, y, w, 18);
    }
  }
  ctx.strokeStyle = '#b84528'; ctx.beginPath(); ctx.moveTo(t / v.duration * width, 0); ctx.lineTo(t / v.duration * width, height); ctx.stroke();
}
let sample, generation = 0;
function update(name) {
  const audio = audioFor(name);
  if (!plans[name]) return;
  controllers[name].setSpeechTime(plans[name].sourceSecondsAt(audio.currentTime));
  $(name + 'Time').textContent = `${audio.currentTime.toFixed(3)} / ${sample[name].duration.toFixed(3)} s`;
  $(name).dataset.audioTime = audio.currentTime;
  const slider = $(name + 'Seek'); if (slider) slider.value = audio.currentTime;
  const phoneme = sample[name].phonemes.find(p => p.start <= audio.currentTime && audio.currentTime < p.end);
  if ($(name + 'Phone')) $(name + 'Phone').textContent = phoneme ? `Fonema /${phoneme.phoneme}/ · forma ${phoneme.shape}` : 'Pausa insertada';
  paint(name, audio.currentTime);
}
function tick() { for (const name of names) if (!audioFor(name).paused) update(name); requestAnimationFrame(tick); }
async function change() {
  if (!controllers.baseline || !controllers.automatic) return;
  const token = ++generation;
  const language = $('language').value, scenario = $('scenario');
  if (scenario && scenario.dataset.language !== language) {
    scenario.replaceChildren(); scenario.dataset.language = language;
    for (const [i, c] of data.cases.entries()) if (c.language === language) {
      const option = document.createElement('option'); option.value = c.id ?? String(i);
      option.textContent = c.label ?? 'Prueba anterior'; scenario.append(option);
    }
  }
  sample = data.cases.find((c, i) => c.language === language && (!scenario || (c.id ?? String(i)) === scenario.value));
  const metrics = data.metrics?.[language];
  if ($('evaluation')) $('evaluation').textContent = metrics
    ? `Resultados en ${metrics.groups} frases test nuevas, anterior → nuevo: concordancia ${metrics.agreement.map(v => (v * 100).toFixed(1) + '%').join(' → ')}; `
      + `F1 macro ${metrics.f1.map(v => (v * 100).toFixed(1) + '%').join(' → ')}; cierres cuando la referencia pide apertura ${metrics.false_closure.map(v => (v * 100).toFixed(1) + '%').join(' → ')}. `
      + `Referencia automática, no calidad visual.${metrics.dev_guardrails_passed === false ? ' El nuevo modelo no pasó todos los límites de cierres en validación.' : ''}`
      + (metrics.pause_interior ? ` Habla medida sin los silencios confirmados; cierre en el interior de todas las pausas (incluye saludo) ${metrics.pause_interior.map(v => (v * 100).toFixed(1) + '%').join(' → ')}.` : '')
      + (metrics.advice_pause_interior ? ` Sólo pausas del consejo: interior ${metrics.advice_pause_interior.map(v => (v * 100).toFixed(1) + '%').join(' → ')}; con bordes incluidos ${metrics.advice_all_pause.map(v => (v * 100).toFixed(1) + '%').join(' → ')}. Estas cifras describen al clasificador, no al avatar renderizado.` : '')
    : '';
  if (data.visualPolicies) $('evaluation').textContent = 'Prueba de selección visual: no cambió la precisión del clasificador. La boca abierta sin visema fino confirmado aparece en naranja. El empalme nuevo es un candidato de mejora, no una garantía perceptual.';
  if ($('accelerate')) $('accelerate').checked = defaults[sample.language].avoidLongClosures;
  $('text').textContent = sample.text;
  $('decisions').replaceChildren();
  for (let i = 0; i < sample.decisions.length; i++) {
    const decision = sample.decisions[i], a = sample.baseline.timing.segments[i], b = sample.automatic.timing.segments[i];
    const row = document.createElement('tr');
    for (const value of [decision.text, decision.factor === 1 ? 'Conservar' : `Reducir ${Math.round((1 - decision.factor) * 100)} %`,
      data.functionalityReview ? `${b.words_per_second.toFixed(2)} palabras/s` : `${a.words_per_second.toFixed(2)} → ${b.words_per_second.toFixed(2)} palabras/s`]) {
      const td = document.createElement('td'); td.textContent = value; row.append(td);
    }
    $('decisions').append(row);
  }
  await Promise.all(names.map(async name => {
    const version = sample[name], audio = $(name + 'Audio'); audio.pause();
    $(name + 'Play').disabled = true;
    controllers[name].setSpeaking(false); controllers[name].setSpeechLanguage(sample.language); controllers[name].setWorking(true);
    const visual = visualFor(name), oldVisual = visualFor('baseline');
    if (data.visualPolicies) controllers[name].setExperimentalSpeechRange(visual.ranges[sample.language].first, visual.ranges[sample.language].end);
    plans[name] = planTiming(cuesFor(version), version.timing, visual.catalogs[sample.language], visual.ranges[sample.language], defaults[sample.language]);
    $(name).dataset.planSignature = plans[name].frames.join(',');
    plans[name + 'Prior'] = planTiming(cuesFor(version, 'previous'), version.timing, oldVisual.catalogs[sample.language], oldVisual.ranges[sample.language], defaults[sample.language]);
    if ($(name + 'Seek')) $(name + 'Seek').max = version.duration;
    const loaded = new Promise((resolve, reject) => { audio.addEventListener('loadedmetadata', resolve, { once: true }); audio.addEventListener('error', reject, { once: true }); });
    audio.src = version.audio; audio.load(); await loaded;
    if (generation !== token) return;
    $(name + 'Play').disabled = false; update(name);
  }));
  $('status').textContent = 'Listo. Cada audio tiene sus propias marcas fonéticas y plan de animación.';
}
for (const name of names) {
  const audio = $(name + 'Audio');
  audio.addEventListener('play', () => {
    names.filter(other => other !== name).forEach(other => $(other + 'Audio').pause());
    for (const target of data.compareModels ? names : [name]) { controllers[target].setWorking(false); controllers[target].setSpeaking(true); }
  });
  audio.addEventListener('pause', () => { refresh(name); for (const target of data.compareModels ? names : [name]) controllers[target]?.setSpeaking(false); });
  audio.addEventListener('seeked', () => { for (const target of data.compareModels ? names : [name]) { controllers[target].setWorking(false); controllers[target].setSpeaking(true); } refresh(name); });
  $(name + 'Play').onclick = async () => {
    names.filter(other => other !== name).forEach(other => $(other + 'Audio').pause());
    audio.currentTime = 0; await audio.play();
  };
  if ($(name + 'Seek')) $(name + 'Seek').oninput = () => { const target = audioFor(name); target.pause(); target.currentTime = Number($(name + 'Seek').value); };
}
if (model) model.onchange = recompute;
if ($('accelerate')) $('accelerate').onchange = recompute;
$('language').onchange = () => change().catch(error => $('status').textContent = error.message);
if ($('scenario')) $('scenario').onchange = () => change().catch(error => $('status').textContent = error.message);
if ($('visualMode')) $('visualMode').onchange = () => change().catch(error => $('status').textContent = error.message);
async function init() {
  for (const name of names) {
    if (data.visualPolicies) $(name).dataset.visualPolicy = name;
    controllers[name] = await createIsaPortrait($(name));
    const canvas = $(name).querySelector('canvas');
    for (const [method, attribute] of [['setSpeaking', 'data-isa-speaking'], ['setSpeechLanguage', 'data-isa-speech-language']]) {
      const original = controllers[name][method].bind(controllers[name]);
      controllers[name][method] = value => { canvas.setAttribute(attribute, String(value)); return original(value); };
    }
    controllers[name].play('isa-awake');
  }
  await change(); tick();
}
if(data.functionalityReview) $('finish').onclick=()=>{
  audioFor('automatic').pause();refresh('automatic');
  for(const name of names)controllers[name].setSpeaking(false);
};
if(data.functionalityReview) $('recover').onclick=async()=>{
  const button=$('recover');button.disabled=true;
  const controls=[$('language'),$('scenario'),$('visualMode'),$('accelerate'),$('automaticPlay'),$('finish')];
  controls.forEach(c=>c.disabled=true);
  audioFor('automatic').pause();
  try{
    for(const name of names){
      controllers[name].destroy();
      controllers[name]=await createIsaPortrait($(name));
      controllers[name].play('isa-awake');controllers[name].setSpeechLanguage(sample.language);
    }
    failingImages=true;
    for(const name of names)controllers[name].setSpeaking(true);
    await new Promise(resolve=>setTimeout(resolve,600));
    for(const name of names)controllers[name].setSpeaking(false);
    failingImages=false;
    await new Promise(resolve=>setTimeout(resolve,300));
    for(const name of names){controllers[name].setSpeaking(true);controllers[name].setSpeechTime(1);}
    await new Promise(resolve=>setTimeout(resolve,900));
    const blends=names.map(name=>Number($(name).querySelector('canvas').dataset.isaSpeechBlend));
    $('recoveryStatus').textContent=`Segunda lectura: referencia ${blends[0]>.9?'recuperada':'sin animación'}; corregida ${blends[1]>.9?'recuperada':'sin animación'}. La comparación normal se restauró.`;
    $('recoveryStatus').dataset.result=blends[0]===0&&blends[1]>.9?'pass':'review';
  }catch(error){$('recoveryStatus').textContent=String(error);}
  finally{
    failingImages=false;
    for(const name of names){controllers[name]?.destroy();controllers[name]=await createIsaPortrait($(name));controllers[name].play('isa-awake');}
    await change();controls.forEach(c=>c.disabled=false);button.disabled=false;
  }
};
init().catch(error => $('status').textContent = String(error));
