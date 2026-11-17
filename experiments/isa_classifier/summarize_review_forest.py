"""Write a factual report after frozen final evaluation and visual checks."""
import argparse
import html
import json
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    args=p.parse_args();root=args.root
    folder=root/'forest-review-v2'
    report=json.loads((folder/'evaluation.json').read_text(encoding='utf8'))
    provenance=json.loads((folder/'run-provenance.json').read_text(encoding='utf8'))
    corpus=json.loads((root/'corpus-review-v2/corpus.json').read_text(encoding='utf8'))
    audio=json.loads((folder/'audio-qa.json').read_text(encoding='utf8'))
    visual=json.loads((root/'forest-visual-review-v2/visual-evaluation.json').read_text(encoding='utf8'))
    texts={}
    for row in corpus['recordings']:
        key=row.get('group_id',row['id'])
        item=texts.setdefault(key,{'language':row['language'],'split':row['split'],
            'advice':row.get('advice',row['text']),'text':row['text'],'recordings':[]})
        item['recordings'].append(row['file'])
    (folder/'reference-texts.json').write_text(json.dumps(texts,ensure_ascii=False,indent=2),encoding='utf8')
    table=[];summary={}
    for language,data in report['languages'].items():
        before=data['identity']['grouped_advice'];after=data['boosted']['grouped_advice']
        summary[language]={'previous_agreement':before['mean_group_agreement'],
           'new_agreement':after['mean_group_agreement'],'previous_f1':before['mean_group_macro_f1'],
           'new_f1':after['mean_group_macro_f1'],'dev_guardrails_passed':data['dev_guardrails_passed'],
           'train':data['train'],'dev':data['dev'],'test':data['test'],'test_groups':data['test_groups']}
        s=summary[language]
        table.append(f"| {language.upper()} | {s['previous_agreement']:.2%} | {s['new_agreement']:.2%} | {s['previous_f1']:.2%} | {s['new_f1']:.2%} | {'Sí' if s['dev_guardrails_passed'] else 'No'} |")
    text=f'''# Random Forest V2 · datos ampliados y referencias verificadas

Nueva versión entrenada desde cero; el modelo V1 y sus audios siguen intactos.
No hubo despliegue ni sustitución de Rhubarb.

## Datos y comparación

- Archivo acumulado: {len(corpus['recordings'])} grabaciones, {sum(r['duration'] for r in corpus['recordings'])/60:.1f} minutos y {len(texts)} grupos.
- Se conservaron {provenance['previous_rows_preserved']} grabaciones previas, sin cambiar sus splits, textos ni PCM.
- Se aceptaron {provenance['new_recordings']} grabaciones de 48 consejos nuevos.
- Entrenamiento: {provenance['split_counts']['train']} grabaciones; validación: {provenance['split_counts']['dev']}.
- Evaluación final nueva: {sum(s['test'] for s in summary.values())} grabaciones, 8 consejos por idioma, sin usarlas para entrenar o seleccionar parámetros.
- Los tests históricos se archivan aparte; no se suman al conjunto final nuevo.
- 92 audios nuevos verificados por Audio Lens, sin clipping; integridad PCM y fonemas de la misma síntesis comprobadas.
- Las variantes de velocidad se promedian por consejo. Se preservan saludo, despedida y pausas.

## Resultados finales

Concordancia con referencia automática Rhubarb y pausas verificadas, **no precisión visual humana**.

| Idioma | Concordancia V1 | Concordancia V2 | F1 macro V1 | F1 macro V2 | Controles de validación |
| --- | ---: | ---: | ---: | ---: | --- |
{chr(10).join(table)}

La evaluación tiene ocho grupos por idioma; no demuestra por sí sola una mejora general.
No se alteraron los hiperparámetros después de consultar estos resultados.

## Animación y límites

Los dos modelos se comparan con el mismo renderer corregido, mismas etiquetas visuales
revisadas y mismo audio. La recuperación de imágenes y de voz sigue siendo lógica del
reproductor, no una etiqueta acústica aprendida. La política de velocidad por frase
y el planificador temporal siguen siendo automatizaciones separadas del bosque.

La auditoría visual recorre cada audio final con V1/V2 y con/sin aceleración local.
Controla avance monotónico, límites de desfase y saltos compatibles con pose/movimiento.
Sus contadores usan formas provisionales; no son un segundo porcentaje de precisión.
La agrupación de marcas menores que un frame sigue pendiente.

No hay mejora uniforme en el indicador visual provisional de cierre durante habla:
ES V1 {visual['summary']['es-previous']['after_ms']:.0f} ms → V2 {visual['summary']['es-boosted']['after_ms']:.0f} ms;
EN V1 {visual['summary']['en-previous']['after_ms']:.0f} ms → V2 {visual['summary']['en-boosted']['after_ms']:.0f} ms,
acumulados sobre 15 grabaciones por idioma. Este indicador compara solicitudes de
cada modelo con etiquetas visuales provisionales, no una verdad humana fija.
La animación requiere revisión perceptiva; el nuevo RF queda como candidato.

Abrir comparación de modelos: `tmp/isa-own-classifier/forest-direct-review-v2/index.html`.
Abrir comparación de velocidades: `tmp/isa-own-classifier/forest-rate-review-v2/index.html`.

Referencias completas de texto: `forest-review-v2/reference-texts.json`.
Métricas y procedencia: `evaluation.json`, `run-provenance.json`, `audio-qa.json`,
`pause-roles.json` y `forest-visual-review-v2/visual-evaluation.json`.
'''
    (folder/'report.md').write_text(text,encoding='utf8')
    (folder/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    (folder/'index.html').write_text('''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Isa · entrenamiento RF V2</title><style>body{font:16px/1.6 system-ui;background:#edf8fc;color:#123952;max-width:1000px;margin:30px auto;padding:16px}pre{white-space:pre-wrap;overflow-wrap:anywhere}a{color:#216f94}</style><h1>Isa · entrenamiento RF V2</h1><p><a href="../forest-direct-review-v2/index.html">Abrir comparación V1 / V2</a> · <a href="../forest-rate-review-v2/index.html">Revisar velocidades</a></p><pre>'''+html.escape(text)+'''</pre></html>''',encoding='utf8')
    print(json.dumps(summary))

if __name__=='__main__':main()
