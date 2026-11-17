# Machine learning por árboles y tiempos · 16/11/2026

Se completó [PROTOCOL-BOOSTED.md](PROTOCOL-BOOSTED.md) con XGBoost 3.4.1 CPU en
el entorno experimental. No se modificaron dependencias de producción ni frontend.

## Qué se entrenó

Nuevo aprendiz de árboles potenciados, usando las mismas señales de identidad
fonética, acústica, ritmo y duración de la ronda anterior. Mantiene vocabularios
exclusivos de train (91 entradas ES, 97 EN) y contexto por archivo, sin juntar
ventanas de grabaciones vecinas. El modelo no reconoce fonemas nuevos por sí
solo: recibe las marcas de la síntesis Piper del mismo PCM.

139 grabaciones train, 32 dev. Cuatro ajustes de árboles por idioma: profundidad
3/5 y balance .25/.5, 160 rondas, hist con 64 bins, eta .08, lambda 10,
min_child_weight 10, subsample .85, colsample .8, semilla 20261116 y dos hilos.
Se conservan peso del consejo 1, saludo/despedida .25 y división por variantes.

Cuatro decodificaciones por ajuste: penalización de cierre 0/.25 y transición
0/.05. Total: 16 candidatos por idioma, elegidos sólo en dev. La calibración
busca evitar cierres incorrectos sin perder pausas ni sonidos bilabiales A.
Los pesos se exportaron como UBJSON nativo, no pickle; el visor usa predicciones
precalculadas y no requiere instalar XGBoost en el navegador.

Referencias de implementación: [parámetros](https://xgboost.readthedocs.io/en/stable/parameter.html)
y [formato de modelos](https://xgboost.readthedocs.io/en/stable/tutorials/saving_model.html).

## Datos nuevos de evaluación

16 consejos exclusivamente test, 8 por idioma. Con las variantes automáticas
aceptadas son 31 audios: 15 ES / 16 EN. Los test anteriores se conservaron sin
trasladarlos a train/dev. El corpus acumulado tiene 291 grabaciones, 216 grupos
y 2489,76 s (41 min 30 s); eso no significa que todos esos audios se entrenen.

La auditoría comprobó hashes, los 75 pares de velocidad acumulados, reducción
real de las frases seleccionadas, pausas insertadas y separación de grupos.
La selección se congeló antes de evaluar los nuevos test. El vocabulario y los
parámetros no se modificaron después de ver sus puntuaciones.

## Resultados: media entre los 8 grupos test de cada idioma

Concordancia con etiquetas Rhubarb débiles, no precisión humana de sincronización.
Todos los modelos se evaluaron sobre exactamente las mismas frases y PCM.

| Variante | ES concordancia | ES F1 macro | EN concordancia | EN F1 macro |
| --- | ---: | ---: | ---: | ---: |
| V7 | 58,18 % | 36,32 % | 56,90 % | 45,14 % |
| Identidad anterior | 58,00 % | 33,55 % | 61,08 % | 48,01 % |
| Árboles + decodificación | 63,71 % | 39,15 % | 61,57 % | 49,11 % |

Frente a identidad anterior: ES +5,72 puntos de concordancia, +5,60 F1; EN
+0,49 puntos de concordancia, +1,10 F1. Mejoran 8/8 grupos españoles y 5/8 ingleses
en concordancia. Las cifras de otras rondas pertenecen a otras frases.

Bootstrap emparejado por grupos (10000 remuestras, exploratorio): intervalo 95 %
del cambio de concordancia ES [4,41; 7,11] puntos, EN [-0,99; 2,00]. El inglés
todavía no demuestra una mejora general concluyente; 8 frases son pocas.
No se llegó a 100 % ni se pretende obtenerlo memorizando test.

## Retrocesos y límites de cierre

En dev ningún candidato español cumplió todos los límites: el mejor F1 pierde
cierre en pausas conocidas (85,60 % -> 78,69 %). Se guardó sólo como diagnóstico,
sin promoverlo. Selección: profundidad 5, balance .25, penalización 0, transición .05.

En inglés sí hubo candidato elegible: profundidad 3, balance .5, penalización .25,
transición .05. Cumplir límites dev no garantiza mejorar cada indicador test.

Test, ventanas con A/X mientras la referencia pide apertura (denominador: todas
las ventanas del consejo): ES 4,64 % -> 3,80 %; EN 5,87 % -> 4,60 %.
Cierre en pausas insertadas: ES 84,23 % -> 79,24 % (retroceso), EN 99,03 % ->
98,64 % (ligero retroceso). Se deben conservar estas métricas separadas del F1.

## Animación: auditoría independiente

124 planes: 31 audios × 2 modelos × con/sin aceleración. Se verificaron saltos
permitidos por pose/movimiento, avance monótono, límites de desplazamiento y reloj
sin retraso acumulado. Son comprobaciones de continuidad, no revisión humana.

En las 16 grabaciones inglesas, la aceleración del modelo nuevo redujo el cierre
visual prolongado heurístico de 8333 ms a 2625 ms acumulados; 15 mejoraron, ninguna
empeoró al activar la función. El modelo anterior termina también en 2625 ms:
**el nuevo clasificador no mejora ese indicador visual final**.

En español la aceleración sigue apagada por defecto. El indicador visual del
nuevo modelo es 8917 ms frente a 8458 ms del anterior (retroceso). Las etiquetas
visuales son aproximadas y el movimiento depende de qué frames estén disponibles
y de sus restricciones. Subir concordancia acústica no basta para prometer mejor
animación. El banco de imágenes no cambió.

## Visor final y comprobaciones

`tmp/isa-own-classifier/boosted-review-v1/index.html`: anterior/nuevo seleccionable,
voz normal/automática, aceleración local, tres muestras por idioma, fonema activo,
barras de energía/pausas/boca solicitada/frame/control y métricas de test por voz.
Cada WAV tiene sus propios tiempos. El controlador de velocidad sigue siendo una
regla de dos pasadas; el aprendizaje automático corresponde al clasificador.

La suite general ejecutó 70 casos con uno omitido porque XGBoost está aislado;
los cuatro específicos se ejecutaron en ese entorno, incluido el caso omitido.
Los 70 casos únicos quedaron cubiertos. Pasaron el planificador y Playwright
ES/EN: audio exclusivo, cambio de modelo sin reinicio, barras pintadas, búsqueda,
muestras nuevas, móvil sin desbordamiento y ausencia de solicitudes externas.

El proceso de entrenamiento observado usó aproximadamente 0,5–0,6 GB de memoria
residente y dos hilos. No es una medición de latencia ni memoria del endpoint de
Render; la integración de producción queda pendiente de revisión visual y técnica.

## Artefactos y reproducción

- `tmp/isa-own-classifier/boosted-v1/`: modelos finales, `evaluation.json`,
  `paired-comparison.json` y predicciones test. Modelo ES ~4 MB, EN ~2,2 MB.
- `corpus-boosted-v1/`: corpus acumulado y auditoría.
- `boosted-visual-v1/`: auditoría de los 124 planes y resultados por caso.
- Dependencias aisladas: [requirements-boosted.txt](requirements-boosted.txt).

```powershell
python experiments/isa_classifier/boosted_test_plan.py tmp/isa-own-classifier/boosted-test-nuevo.json
.\tmp\isa-phoneme-env\Scripts\python.exe -X utf8 experiments/isa_classifier/generate_rate_expansion.py --previous tmp/isa-own-classifier/corpus-identity-v1/corpus.json --plan tmp/isa-own-classifier/boosted-test-nuevo.json --output tmp/isa-own-classifier/corpus-boosted-nuevo
python experiments/isa_classifier/audit_rate_corpus.py tmp/isa-own-classifier/corpus-boosted-nuevo/corpus.json
```

Sólo después de auditoría correcta:

```powershell
.\tmp\isa-phoneme-env\Scripts\python.exe -X utf8 experiments/isa_classifier/train_boosted.py --corpus tmp/isa-own-classifier/corpus-boosted-nuevo/corpus.json --reference tmp/isa-own-classifier/hybrid-identity-v2 --v7 tmp/isa-own-classifier/v7 --output tmp/isa-own-classifier/boosted-nuevo
```

Producción y los modelos anteriores se conservan. La prioridad pendiente es el
cierre real en pausas españolas y la correspondencia entre marcas y frames.
