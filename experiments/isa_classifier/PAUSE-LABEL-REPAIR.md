# Primera etapa: etiquetas de pausas verificadas · 16/11/2026

Se completó [PROTOCOL-PAUSE-REPAIR.md](PROTOCOL-PAUSE-REPAIR.md): corregir primero
la supervisión de pausas, conservando la familia de modelo y configuraciones.
Random Forest y la red temporal no se entrenaron en esta etapa para aislar el
efecto de reparar etiquetas.

## Correcciones con procedencia comprobable

Se aceptan pausas declaradas por `isac` y gaps de 20/80 ms entre chunks en la
cobertura fonética del mismo WAV. Se exige hash del PCM original, tiempos en
la rejilla de muestras y PCM exactamente cero en todo el intervalo.

Sólo se relabelan como X las ventanas acústicas cuyo soporte completo de 40 ms
está dentro del silencio insertado. El cálculo usa el padding/índices reales de
`audio_features`, no supone que el timestamp mostrado sea el centro exacto de
la ventana. Una pausa de 20 ms no genera por sí sola ventanas de 40 ms fiables.

No se convierten en silencio puntuación, baja energía, ceros naturales dentro de
un fonema ni consonantes suaves/oclusiones. Las etiquetas fuera de la máscara
segura y todos los audios originales permanecen intactos.

En los 139 audios train se corrigieron **570 ventanas**: 360 ES y 210 EN.
Entre ellas había 342 ES y 184 EN etiquetadas como boca abierta dentro de PCM
silencioso confirmado. El resto era A (labios apretados), que se normaliza a X
(reposo) sólo en esos silencios conocidos. No son 570 palabras ni 570 audios.

Se conservaron las correcciones como sidecar con índice de ventana, tiempo,
etiqueta anterior/nueva, intervalo y fuente: `tmp/isa-own-classifier/pause-labels-v1/pause-label-audit.json`.
Las etiquetas Rhubarb originales no se sobreescribieron.

## Comparación controlada

Se reentrenó el mismo XGBoost con configuraciones congeladas de `boosted-v1`,
misma semilla, rondas, features, grupos y pesos de enfoque. Sólo cambiaron los
targets fiables y los pesos por clase/transiciones derivados de esos targets.
Sin forzar la predicción a X ni buscar nuevos hiperparámetros mirando test.

Train 139 / dev 32, sin trasladar test. Se generaron 16 consejos nuevos sólo test
(8 por idioma), con 31 renders baseline/auto válidos. Corpus acumulado: 322 WAV,
232 grupos y 2770,38 s; no se entrenan todos esos WAV. La auditoría verificó
los 90 pares de velocidad acumulados y la separación de grupos.

La métrica primaria excluye todas las pausas insertadas verificadas del consejo,
para que acertar silencio conocido no infle el porcentaje de habla. Los dos
modelos se evalúan en el mismo PCM y con las mismas máscaras. Las pausas se
miden aparte. El resto de etiquetas sigue siendo Rhubarb débil, no verdad humana.

## Habla del consejo, sin pausas verificadas: 8 grupos por idioma

| Modelo | ES concordancia | ES F1 macro | EN concordancia | EN F1 macro |
| --- | ---: | ---: | ---: | ---: |
| XGBoost anterior | 59,98 % | 36,79 % | 58,99 % | 45,79 % |
| Mismo modelo, pausas reparadas | 59,95 % | 36,87 % | 59,01 % | 45,49 % |

Habla prácticamente estable; no se atribuye una mejora general de clasificación.
Los intervalos bootstrap emparejados del cambio de concordancia incluyen cero:
ES [-.52; .53] puntos, EN [-.44; .44]. No comparar con porcentajes de otras frases.

## Cierre predicho en pausas: mejora parcial y bordes pendientes

| Ámbito | ES anterior → reparado | EN anterior → reparado |
| --- | ---: | ---: |
| Interior confirmado de todas las pausas (incluye saludo) | 95,33 → 100 % | 96,88 → 98,96 % |
| Interior confirmado de pausas del consejo | 96,74 → 100 % | 100 → 100 % |
| Pausas del consejo, incluidos bordes | 77,25 → 79,22 % | 99,23 → 98,47 % |
| Pausas de segmento tradicionales, incluido saludo | 79,00 → 82,40 % | 94,93 → 96,49 % |

Los 100 % de esta tabla son submétricas de silencio insertado, no precisión
global, sincronización humana ni boca renderizada. En inglés, parte de la mejora
agregada está en el saludo; el consejo ya tenía interior correcto y retrocede
ligeramente en bordes. La separación evita inflar el avance con frases repetidas.

Ambos idiomas pasan los controles de validación con la configuración congelada.
En habla, el indicador de cierres cuando la referencia pide apertura cambia ES
3,35 -> 3,29 % y EN 3,73 -> 3,86 % (ligero retroceso inglés).

## Renderizado: el selector sigue limitando el resultado

Se auditaron 124 planes: 31 audios × dos modelos × con/sin aceleración. Ambos
usan las mismas pausas verificadas, incluidos chunks, para comparar con justicia.
Se verificaron continuidad, uniones de pose/movimiento y desplazamiento acotado.

Con los perfiles actuales, los frames etiquetados como cerrados durante pausas
confirmadas pasan ES 68/124 a 70/124 instantes (54,84 -> 56,45 %), EN 74/128 en
ambos (57,81 %). Son etiquetas visuales provisionales muestreadas a 24 fps.
Este indicador muestra por qué el acierto del clasificador en silencio no basta:
el selector no siempre elige/alcanza el frame cerrado en el instante solicitado.

En inglés, la aceleración reduce el cierre prolongado sobre habla del modelo
reparado de 7917 a 2333 ms acumulados. El anterior termina en 2375 ms. Español
conserva aceleración apagada por defecto: el indicador pasa de 9542 a 9417 ms.
Son auditorías heurísticas, no revisión humana de labios.

## Visor y validación

`tmp/isa-own-classifier/pause-repair-review-v1/index.html` conserva voz actual/auto,
aceleración local, modelos anterior/nuevo, tres muestras por idioma, fonema activo
y barras de energía/pausas/boca/frame/control. Las métricas separan saludo/consejo,
interior/bordes y clasificador/render. Cada audio tiene sus propios tiempos.

75 casos unitarios cubiertos: la suite general omite el caso de XGBoost aislado,
que se ejecuta junto a los cuatro específicos en ese entorno. Pasaron las pruebas
del visor en ES/EN y las de continuidad de los 124 planes. No se cambiaron
producción, frontend ni banco de imágenes.

Artefactos finales: `boosted-pause-repair-v1/evaluation.json`, `pause-roles.json`,
`paired-comparison.json`, modelos y predicciones, bajo `tmp/isa-own-classifier/`;
`pause-repair-visual-v1/visual-evaluation.json` para los frames.

## Reproducir

```powershell
python experiments/isa_classifier/pause_test_plan.py tmp/isa-own-classifier/pause-test-nuevo.json
.\tmp\isa-phoneme-env\Scripts\python.exe -X utf8 experiments/isa_classifier/generate_rate_expansion.py --previous tmp/isa-own-classifier/corpus-boosted-v1/corpus.json --plan tmp/isa-own-classifier/pause-test-nuevo.json --output tmp/isa-own-classifier/corpus-pause-nuevo
python experiments/isa_classifier/audit_rate_corpus.py tmp/isa-own-classifier/corpus-pause-nuevo/corpus.json
python experiments/isa_classifier/audit_pause_labels.py --corpus tmp/isa-own-classifier/corpus-pause-nuevo/corpus.json --output tmp/isa-own-classifier/pause-labels-nuevo
```

Después de que ambas auditorías terminen correctamente:

```powershell
.\tmp\isa-phoneme-env\Scripts\python.exe -X utf8 experiments/isa_classifier/train_boosted.py --corpus tmp/isa-own-classifier/corpus-pause-nuevo/corpus.json --reference tmp/isa-own-classifier/boosted-v1 --v7 tmp/isa-own-classifier/v7 --verified-pauses --fixed-configuration tmp/isa-own-classifier/boosted-v1 --output tmp/isa-own-classifier/pause-models-nuevo
```

Siguiente etapa: comparar familias sobre estas mismas correcciones de pausa,
empezando por Random Forest frente a XGBoost; después, red temporal pequeña.
La selección visual es un problema aparte que esas comparaciones no deben ocultar.
