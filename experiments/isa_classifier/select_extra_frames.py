"""Select a small non-duplicate set from verified existing take-2/3 frame caches."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from classifier import classify
from review_images import encoded, image_features


def pose_features(image):
    rgb = image.convert('RGB')
    # Keep body/head alignment in the descriptor; exclude the mouth rectangle.
    small = np.asarray(rgb.resize((20, 20)), dtype=float) / 255
    small[6:10, 7:13] = 0
    return small.flatten()


def select(candidates, current, counts, limit):
    selected = []
    coverage, takes = Counter(), Counter()
    for candidate in candidates:
        candidate['pose_distance'] = float(np.sqrt(np.min(np.mean(
            (current['pose'] - candidate['pose']) ** 2, axis=1))))
    # This is a screening criterion, not a guarantee of seamless transitions.
    pool = [c for c in candidates if c['pose_distance'] <= .10]
    while pool and len(selected) < limit:
        choices = []
        for candidate in pool:
            if takes[candidate['take']] >= (limit + 1) // 2:
                continue
            if any(c['take'] == candidate['take'] and abs(c['frame'] - candidate['frame']) < 6 for c in selected):
                continue
            references = np.vstack([current['mouth'], *[c['mouth'][None, :] for c in selected]])
            novelty = float(np.sqrt(np.min(np.mean((references - candidate['mouth']) ** 2, axis=1))))
            if novelty < .015:
                continue
            shape = candidate['proposal']
            score = novelty / np.sqrt(counts[shape] + 1) / (1 + coverage[shape])
            score /= 1 + candidate['pose_distance'] * 10
            choices.append((score, candidate, novelty))
        if not choices:
            break
        _, best, novelty = max(choices, key=lambda c: c[0])
        best['novelty'] = novelty
        selected.append(best)
        coverage[best['proposal']] += 1
        takes[best['take']] += 1
        pool = [c for c in pool if c is not best]
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frontend', type=Path, required=True)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--limit', type=int, default=24)
    args = parser.parse_args()
    if not 1 <= args.limit <= 48:
        parser.error('Select between 1 and 48 candidates')
    frontend = args.frontend.resolve()
    model = json.loads(args.model.read_text())
    if model.get('modality') != 'image' or model.get('language') != 'es':
        parser.error('Use the visual model for the current Spanish takes')
    roi = model['roi']
    manifest = json.loads((frontend / 'src/app/shared/isabel/isa-speech-manifest.json').read_text())
    catalog = json.loads((frontend / 'src/app/shared/isabel/isa-speech-selection.json').read_text())
    counts = Counter(catalog['labels'])
    poses, mouths = [], []
    for page in manifest['pages']:
        with Image.open(frontend / 'public' / page['image']) as atlas:
            for local in range(page['count']):
                x, y = local % 8 * 320, local // 8 * 320
                image = atlas.crop((x, y, x + 320, y + 320))
                mouths.append(image_features(image.crop(roi)))
                poses.append(pose_features(image))
    current = {'pose': np.array(poses), 'mouth': np.array(mouths)}
    candidates, provenance = [], []
    for take in (2, 3):
        source = frontend / f'public/isa-bot/isa-hablando{take}-video.mp4'
        cache = frontend / f'tmp/isa-mouth-preview/video-{take}'
        identity = json.loads((cache / 'fusion-cache.json').read_text())
        if identity['sha256'] != hashlib.sha256(source.read_bytes()).hexdigest():
            raise ValueError('Source video changed; rebuild the cached frames first')
        provenance.append({'take': take, 'source': source.name, **identity})
        for page in range(5):
            with Image.open(cache / f'fusion-speech-{page}.webp') as atlas:
                for local in range(48):
                    frame = page * 48 + local
                    if not 12 <= frame < 228:
                        continue  # Omit opening/closing idle, as in the current bank.
                    x, y = local % 8 * 320, local // 8 * 320
                    image = atlas.crop((x, y, x + 320, y + 320))
                    candidates.append({'take': take, 'frame': frame,
                        'mouth': image_features(image.crop(roi)), 'pose': pose_features(image), 'image': image.copy()})
    predicted, margins = classify(model, [c['mouth'] for c in candidates])
    for candidate, shape, margin in zip(candidates, predicted, margins):
        candidate.update(proposal=str(shape), margin=float(margin))
    selected = select(candidates, current, counts, args.limit)
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    for candidate in selected:
        filename = f"take-{candidate['take']}-frame-{candidate['frame']:03d}.webp"
        candidate['image'].save(args.output / filename, quality=90)
        rows.append({k: candidate[k] for k in ('take', 'frame', 'proposal', 'margin', 'pose_distance', 'novelty')}
                    | {'file': filename, 'reviewed': False,
                       'image': encoded(candidate['image'].resize((240, 240)))})
    report = {'analyzed': len(candidates), 'selected': len(rows), 'limit': args.limit,
        'reference_bank_frames': len(mouths), 'reference_weak_label_counts': dict(counts),
        'provenance': provenance, 'policy': 'mouth novelty, scarce provisional shapes, pose screen, minimum 6-frame spacing, take cap',
        'warning': 'proposals only; not automatically added to training or production; not a transition quality score',
        'frames': [{k: v for k, v in row.items() if k != 'image'} for row in rows]}
    (args.output / 'extra-frames.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    payload = json.dumps(rows).replace('<', '\\u003c')
    html = '''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Isa · selección reducida de otras tomas</title><style>body{background:#edf8fc;color:#123952;font:16px system-ui;margin:24px}
main{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}article{border:1px solid #8bb6ca;border-radius:16px;padding:12px}
img{width:240px;height:240px}h2{font-size:18px}</style><h1>Isa · pocos frames que aporten variedad</h1>
<p>Se analizaron dos tomas adicionales. Sólo se guardan los candidatos seleccionados por novedad de boca y compatibilidad aproximada de pose.
Las etiquetas son propuestas automáticas sin revisar. No se agregan al banco publicado ni al entrenamiento acústico.</p>
<p>Estas tomas no aportan pares de voz Cori/Sharvard con tiempos verificados. Más imágenes pueden ampliar formas y expresiones, pero no sustituyen los audios etiquetados.</p>
<a href="index.html">Volver a voz y animación juntas</a><main></main><script>
const rows=PAYLOAD;for(const frame of rows){const card=document.createElement('article');
const h=document.createElement('h2');h.textContent='Toma '+frame.take+' · frame '+frame.frame;card.append(h);
const image=document.createElement('img');image.src='data:image/jpeg;base64,'+frame.image;image.alt='Frame completo candidato de Isa';card.append(image);
const p=document.createElement('p');p.textContent='Forma propuesta: '+frame.proposal+' · distancia de pose: '+frame.pose_distance.toFixed(3)+' · pendiente de revisión';card.append(p);document.querySelector('main').append(card)}
</script></html>'''.replace('PAYLOAD', payload)
    (args.output / 'extra-frames.html').write_text(html, encoding='utf8')
    print(json.dumps({'analyzed': len(candidates), 'selected': len(selected),
                      'shapes': dict(Counter(c['proposal'] for c in selected))}))


if __name__ == '__main__':
    main()
