"""Local evidence index; no production assets or analysis results modified."""
import html
import json
from pathlib import Path
import sys

root=Path(sys.argv[1])
summary=json.loads((root/'summary.json').read_text(encoding='utf8'))
audios=json.loads((root/'audio-audit.json').read_text(encoding='utf8'))
links=''.join(f'<li><a href="audio/{html.escape(row["id"])}/prosody/report.html">{html.escape(row["id"])}</a></li>'
              for row in audios if row['prosody'])
rates=''.join(f'<tr><td>{lang.upper()}</td><td>{data["audio"]["rate"]["baseline"]["advice_wps"]["median"]:.2f}</td>'
              f'<td>{data["audio"]["rate"]["automatic"]["advice_wps"]["median"]:.2f}</td>'
              f'<td>{data["facial"]["cycle"]["seam_vs_adjacent_p95"]:.2f}×</td></tr>'
              for lang,data in summary['languages'].items())
page='''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Isa · relevamiento de voz y animación</title>
<style>body{font:16px/1.6 system-ui,sans-serif;background:#edf8fc;color:#123952;margin:24px}main{max-width:1000px;margin:auto}h1,h2{line-height:1.2}a{color:#1e6d93}summary{cursor:pointer;padding:12px 0}img{display:block;max-width:100%;height:auto;border-radius:8px}table{width:100%;border-collapse:collapse}td,th{padding:12px 6px;text-align:left;border-bottom:1px solid #b8dce9}section{margin:36px 0}.note{border-left:3px solid #3297b5;padding-left:16px}figure{margin:16px 0}.table{overflow-x:auto}@media(max-width:500px){body{margin:12px}h1{font-size:28px}td,th{font-size:14px}}</style>
<main><p>17 de noviembre de 2026 · auditoría local</p><h1>Isa: qué funciona y dónde conviene mejorar</h1>
<p class="note">La voz está limpia en las muestras. Las principales oportunidades están en las etiquetas de boca y en el recorrido de los frames. Este relevamiento no reentrena modelos ni modifica producción.</p>
<p>Se revisaron 32 audios, ocho informes de prosodia y 408 frames. Se reconstruyeron 64 planes finales con RF y TDNN.</p>
<section><h2>Lo que merece atención primero</h2><ol>
<li><strong>Etiquetas visuales:</strong> algunos frames abiertos reciben X (reposo). Ver ES #51/#86 y EN #43 en las láminas. Son casos para revisión, no etiquetas nuevas automáticas.</li>
<li><strong>Empalme inglés:</strong> al repetir el ciclo, el cambio facial es 2,55 veces el percentil 95 de las transiciones habituales. Revisar salida/entrada y movimiento de cabeza/párpados.</li>
<li><strong>Recorrido limitado:</strong> la boca pedida no siempre está cerca en el ciclo fijo. Probar secuencias cortas compatibles después de revisar las etiquetas.</li>
<li><strong>Ritmo inglés:</strong> baja con la automatización, pero algunas frases siguen rápidas. Medir la segunda síntesis antes de decidir otra reducción.</li></ol></section>
<section><h2>Voz y repetición del ciclo</h2><p>Cero muestras saturadas en los 32 WAV. Ritmo: mediana de palabras por segundo del consejo; no incluye saludo ni despedida.</p>
<div class="table"><table><thead><tr><th>Idioma</th><th>Ritmo original</th><th>Ritmo ajustado</th><th>Empalme / P95 vecinos</th></tr></thead><tbody>RATES</tbody></table></div>
<p>La columna del empalme mide cambios de píxeles en la cara, excluyendo la boca. No es precisión de un modelo ni una valoración humana.</p></section>
<section><h2>Frames para revisar</h2><p>Las etiquetas son provisionales. La mandíbula ayuda a encontrar candidatos, pero no identifica por sí sola todos los visemas. Los números son índices del atlas.</p>
<details><summary>Ver español: boca, ojos y bordes del ciclo</summary><figure><img src="frame-contact-es.png" alt="Frames españoles con rostro completo y detalle de boca"><figcaption>La X significa reposo; la lámina muestra casos donde su propagación al frame vecino necesita revisión.</figcaption></figure></details>
<details><summary>Ver inglés: boca, ojos y bordes del ciclo</summary><figure><img src="frame-contact-en.png" alt="Frames ingleses con rostro completo y detalle de boca"></figure></details>
<p>No borrar los parpadeos. Tampoco eliminar automáticamente los duplicados: el pHash agrupó los 408 frames juntos porque la escena es casi fija.</p></section>
<section><h2>Informes de voz para explorar</h2><p>Contienen reproducción local, gráficos y texto aproximado. El pitch es una estimación básica; cinco informes alcanzaron un límite del buscador. Sus pausas de al menos 250 ms no sustituyen las marcas precisas de Piper.</p><ul>LINKS</ul></section>
<section><h2>Detalle y datos</h2><ul><li><a href="../../../experiments/isa_classifier/SKILLS-AUDIT.md">Relevamiento completo y prioridades</a></li><li><a href="summary.json">Mediciones resumidas en JSON</a></li><li><a href="../neural-direct-v1/index.html">Comparación RF / red temporal con un solo audio</a></li></ul>
<p>Los informes de voz incluyen audios de prueba incrustados; permanecen locales. No hubo llamadas a servicios de análisis externos. Detectar todos los rostros no garantiza etiquetas correctas para el estilo de Isa.</p></section></main></html>'''
(root/'index.html').write_text(page.replace('RATES',rates).replace('LINKS',links),encoding='utf8')
print(root/'index.html')
