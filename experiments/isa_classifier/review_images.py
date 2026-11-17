"""Produce local, editable frame-label review sheets, never production assets."""

import argparse
import base64
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image

from classifier import SHAPES, classify, fit


def image_features(image):
    # A fixed mouth ROI only: body, eye and eyebrow continuity remains the
    # responsibility of the existing whole-frame selectors, not this classifier.
    small = np.asarray(image.convert('RGB').resize((16, 8)), dtype=float) / 255
    luminance = small.mean(axis=2)
    return np.concatenate([small.flatten(), np.diff(luminance, axis=0).flatten(),
                           np.diff(luminance, axis=1).flatten()])


def encoded(image):
    buffer = io.BytesIO()
    image.convert('RGB').save(buffer, format='JPEG', quality=80)
    return base64.b64encode(buffer.getvalue()).decode('ascii')


def build(frontend, language, output, roi, reviewed=None):
    source = frontend / 'src/app/shared/isabel'
    suffix = '-en' if language == 'en' else ''
    catalog = json.loads((source / f'isa-speech-selection{suffix}.json').read_text(encoding='utf8'))
    manifest = json.loads((source / f'isa-speech-manifest{suffix}.json').read_text(encoding='utf8'))
    labels = dict(zip(catalog['candidates'], catalog['labels']))
    if reviewed is not None:
        approved = json.loads(reviewed.read_text(encoding='utf8'))
        if (approved.get('language') != language or approved.get('version') != 1
                or approved.get('source') != 'human-reviewed' or approved.get('roi') != roi):
            raise ValueError('Reviewed labels must match language, version and mouth ROI')
        labels = {}
        for row in approved['labels']:
            index, value = row['frame'], row['value']
            if (type(index) is not int or not 0 <= index < len(manifest['sourceFrames'])
                    or index in labels or not isinstance(value, str) or value not in SHAPES
                    or row.get('reviewed') is not True):
                raise ValueError('Invalid or duplicate reviewed label')
            labels[index] = value
        if len(set(labels.values())) < 2:
            raise ValueError('Review at least two different mouth shapes before training')
    pages, rows = {}, []
    try:
        # Catalog/page indices address the runtime atlas, not original video
        # frames (the source video has a trimmed lead-in of twelve frames).
        for index, source_frame in enumerate(manifest['sourceFrames']):
            page = next(p for p in manifest['pages'] if p['first'] <= index < p['first'] + p['count'])
            if page['image'] not in pages:
                pages[page['image']] = Image.open(frontend / 'public' / page['image'])
            local = index - page['first']
            width, height, columns = manifest['width'], manifest['height'], manifest['columns']
            x, y = local % columns * width, local // columns * height
            frame = pages[page['image']].crop((x, y, x + width, y + height))
            mouth = frame.crop(roi)
            rows.append({'index': index, 'sourceFrame': source_frame, 'features': image_features(mouth),
                         'image': encoded(frame.resize((160, 160))),
                         'mouth': encoded(mouth.resize((140, 80))),
                         'reference': labels.get(index)})
    finally:
        for page in pages.values():
            page.close()
    anchors = [row for row in rows if row['reference'] in SHAPES]
    model = fit([r['features'] for r in anchors], [r['reference'] for r in anchors])
    model.update(language=language, modality='image', roi=roi,
                 reference='human-reviewed' if reviewed else 'existing provisional labels; manual review required')
    predicted, margins = classify(model, [r['features'] for r in rows])
    for row, label, margin in zip(rows, predicted, margins):
        del row['features']
        row.update(proposal=str(label), margin=round(float(margin), 4))
    output.mkdir(parents=True, exist_ok=True)
    (output / f'image-{language}.json').write_text(json.dumps(model, indent=2), encoding='utf8')
    # The embedded values are generated locally, never remote/user HTML.
    payload = json.dumps({'language': language, 'roi': roi, 'frames': rows}).replace('<', '\\u003c')
    html = '''<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Isa · revisión de etiquetas propias</title>
<style>body{background:#edf8fc;color:#123952;font:16px system-ui;margin:24px}
main{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
article{border:1px solid #9acada;border-radius:8px;padding:12px}img{vertical-align:middle}
select,button{font:inherit;padding:8px;border-radius:8px}header{max-width:900px;margin-bottom:24px}
small,label{display:block}article:has(select[data-mouth]:valid){border-color:#167052}</style>
<header><h1>Isa · etiquetas visuales propias</h1>
<p>Prototipo. Las propuestas aprenden de etiquetas anteriores provisionales, no son validaciones.
Revisá que el recorte incluya la boca en cada idioma. Ojos, expresión y pose se anotan por separado;
todavía no hay un modelo entrenado para esos atributos.</p>
<p>A: labios cerrados · B: estrecha · C: abierta media · D: abierta amplia · E: redondeada ·
F: fruncida · G: labio/dientes · H: lengua · X: reposo. Son códigos de compatibilidad;
no representan letras del texto.</p><button id="export">Descargar etiquetas revisadas</button>
<p id="status" role="status"></p></header><main></main><script>
const data=PAYLOAD;
const root=document.querySelector('main');
for(const frame of data.frames){
 const card=document.createElement('article');
 const title=document.createElement('h2');title.textContent='Frame '+frame.index;card.append(title);
 for(const key of ['image','mouth']){const img=document.createElement('img');
 img.src='data:image/jpeg;base64,'+frame[key];img.alt=key==='image'?'Rostro y postura':'Recorte de boca';
 img.loading='lazy';card.append(img)}
 const note=document.createElement('p');note.textContent='Propuesta: '+frame.proposal+
 ' · referencia provisional: '+(frame.reference??'sin etiqueta')+' · margen: '+frame.margin;card.append(note);
 const label=document.createElement('label');label.textContent='Etiqueta revisada: ';
 const select=document.createElement('select');select.required=true;select.dataset.frame=frame.index;select.dataset.mouth='true';
 for(const value of ['','A','B','C','D','E','F','G','H','X']){const option=document.createElement('option');
 option.value=value;option.textContent=value||'Pendiente de revisión';select.append(option)}
 label.append(select);card.append(label);
 for(const [key,title,options] of [
  ['eyes','Ojos',[['open','Abiertos'],['half','Entreabiertos'],['closed','Cerrados']]],
  ['expression','Expresión',[['neutral','Neutra'],['smile','Sonrisa'],['serious','Seria'],['other','Otra']]],
  ['pose','Cabeza',[['neutral','Frontal/neutra'],['left','Hacia la izquierda de la imagen'],['right','Hacia la derecha de la imagen'],['up','Arriba'],['down','Abajo'],['other','Otra']]]]){
   const field=document.createElement('label');field.textContent=title+' revisado: ';
   const input=document.createElement('select');input.dataset.attribute=key;input.dataset.frame=frame.index;
   for(const [value,text] of [['','Pendiente'],...options]){const option=document.createElement('option');option.value=value;option.textContent=text;input.append(option)}
   field.append(input);card.append(field);
 }
 root.append(card);
}
document.querySelector('#export').onclick=()=>{
 const labels=Array.from(document.querySelectorAll('select[data-mouth]')).filter(s=>s.value)
 .map(s=>({frame:Number(s.dataset.frame),value:s.value,reviewed:true}));
 const attributes=Array.from(document.querySelectorAll('select[data-attribute]')).filter(s=>s.value)
 .map(s=>({frame:Number(s.dataset.frame),attribute:s.dataset.attribute,value:s.value,reviewed:true}));
 const result={version:1,language:data.language,roi:data.roi,source:'human-reviewed',labels,attributes};
 const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));
 const a=document.createElement('a');a.href=url;a.download='isa-labels-'+data.language+'.json';a.click();
 setTimeout(()=>URL.revokeObjectURL(url),1000);
 document.querySelector('#status').textContent=labels.length+' bocas y '+attributes.length+' atributos revisados exportados; '+
 (data.frames.length-labels.length)+' pendientes.';
};</script></html>'''.replace('PAYLOAD', payload)
    target = output / f'review-{language}.html'
    target.write_text(html, encoding='utf8')
    print(json.dumps({'review': str(target), 'frames': len(rows), 'anchors': len(anchors),
                      'reference': model['reference']}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frontend', type=Path, required=True)
    parser.add_argument('--language', choices=('es', 'en'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--labels', type=Path, help='Previously exported human-reviewed labels')
    parser.add_argument('--roi', nargs=4, type=int, default=[120, 111, 190, 151],
                        metavar=('LEFT', 'TOP', 'RIGHT', 'BOTTOM'))
    args = parser.parse_args()
    if not 0 <= args.roi[0] < args.roi[2] <= 320 or not 0 <= args.roi[1] < args.roi[3] <= 320:
        parser.error('ROI must be inside the 320x320 frame')
    build(args.frontend.resolve(), args.language, args.output, args.roi, args.labels)


if __name__ == '__main__':
    main()
