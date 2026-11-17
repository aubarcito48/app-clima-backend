# Random Forest V2 · 17 de noviembre de 2026

Se entrenaron bosques nuevos desde cero con el corpus anterior y consejos
adicionales. RF V1 se conserva intacto. La mejora acústica es modesta y la
selección visual sigue teniendo limitaciones: V2 queda como candidato local.

Protocolo fijado antes de sintetizar: [PROTOCOL-FOREST-REVIEW-V2.md](PROTOCOL-FOREST-REVIEW-V2.md).
Textos nuevos: [review_training_plan.py](review_training_plan.py).

## Datos y evaluación

- 48 consejos nuevos, 24 por idioma: 12 de entrenamiento, 4 de validación y 8
  de evaluación final por idioma. Las variantes de velocidad permanecen juntas.
- 96 audios generados; 92 aceptados. Cuatro variantes de reducción de velocidad
  se excluyeron al no confirmar la reducción en los tiempos reales de las frases.
- Archivo acumulado: 478 grabaciones, 312 grupos y 70,4 minutos. Se conservaron
  386 grabaciones previas, sus textos, divisiones e integridad PCM.
- Entrenamiento efectivo: 186 grabaciones (90 ES / 96 EN); validación: 47
  (23 ES / 24 EN). Evaluación final nueva: 30 grabaciones y 16 grupos de consejo.
  Los 215 tests históricos restantes se archivan y no se mezclan en ese resultado.
- Saludo/despedida exactos de la app; fonemas, ritmo y pausas de la misma síntesis.
  Se reparan sólo interiores de pausas comprobadas mediante PCM y metadatos.

Misma cuadrícula RF de 120 árboles, profundidades 12/20 y hojas 3/8: ocho
bosques ajustados en total, con 32 configuraciones de decodificación evaluadas
únicamente en validación. No se reajustó nada a partir de los resultados finales.

| Idioma | Concordancia V1 | Concordancia V2 | F1 macro V1 | F1 macro V2 |
| --- | ---: | ---: | ---: | ---: |
| Español | 62,54 % | 64,05 % | 37,07 % | 37,44 % |
| Inglés | 61,07 % | 62,60 % | 52,06 % | 52,89 % |

Ambos candidatos pasan los controles de validación relativos a V1. Seleccionan
profundidad 20, hoja 3 y transición 0,05, conservando el balance por idioma.
Los porcentajes son concordancia con Rhubarb y pausas verificadas, no calidad
visual ni precisión humana. Ocho grupos por idioma no justifican generalizar
la ventaja a todos los consejos.

## Integración de las correcciones

Los dos modelos se comparan con idéntico audio, renderer corregido y catálogo
visual revisado. El ritmo automático de voz y la aceleración local de cierres
siguen activos como automatizaciones independientes, no como políticas que el
bosque haya aprendido. Las correcciones de red, autoplay e imágenes tampoco
se convierten artificialmente en etiquetas de entrenamiento acústico.

Se verificaron 120 planes visuales (30 audios × dos modelos × con/sin aceleración)
con avance monotónico, límites de desfase y saltos compatibles con pose/movimiento.
El indicador provisional de cierres durante solicitudes de apertura no mejora
uniformemente: ES V1/V2 acumulan 9750/10083 ms; EN 1750/1875 ms. Usa solicitudes
propias de cada modelo y formas visuales provisionales; requiere revisión perceptiva.
La agrupación de marcas menores que un frame permanece pendiente.

## Verificación y artefactos

- 84 pruebas experimentales correctas en el entorno aislado.
- Audio Lens: 92 WAV nuevos sin clipping, picos entre −7,26 y −3,54 dBFS.
- Exportación portable contrastada con sklearn con tolerancia de 1e-12.
- Visores comprobados: reproducción, reloj común, búsqueda temporal, barras,
  idiomas/muestras, móvil y ausencia de errores JavaScript o consultas externas.
- Modelos anteriores verificados por hash; producción y banco publicado sin cambios.

Comparación directa: `tmp/isa-own-classifier/forest-direct-review-v2/index.html`.
Comparación de velocidades: `tmp/isa-own-classifier/forest-rate-review-v2/index.html`.
Informe completo: `tmp/isa-own-classifier/forest-review-v2/index.html`.
Los modelos JSON pesan unos 28,2 MB ES y 28,8 MB EN; falta medir su coste en Render.

En `forest-review-v2/`: `evaluation.json`, `run-provenance.json`, `audio-qa.json`,
`pause-roles.json`, `reference-texts.json` (todos los textos anteriores/nuevos)
y `summary.json`. En `forest-visual-review-v2/`: auditoría de todos los audios finales.

Reproducción: `generate_rate_expansion.py --parallel-languages`,
`run_review_forest.py`, `finish_review_forest.py` y `summarize_review_forest.py`.
Sus argumentos señalan el corpus/modelo anteriores y directorios nuevos; no
sobrescribir experimentos previos. Las correcciones pertenecen al laboratorio,
no se sustituyó Rhubarb ni se desplegó V2.
