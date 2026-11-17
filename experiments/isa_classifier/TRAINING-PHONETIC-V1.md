# Híbrido de voz, tiempos y fonética · 16/11/2026

Se entrenaron dos modelos propios, uno por idioma, bajo el protocolo fijado en
[PROTOCOL-PHONETIC-TRAINING.md](PROTOCOL-PHONETIC-TRAINING.md).

## Datos y entradas

128 audios nuevos, 1013,60 segundos en total, regenerando las frases de V7 con
sus mismos splits. Por idioma: 40 train, 8 dev, 16 test. El test conserva frases
reservadas para entrenamiento, pero ya evaluadas antes: es una reevaluación
exploratoria, no evidencia de generalización sobre frases externas nuevas.

Todos incluyen saludo, consejo corto y despedida de la app. Las duraciones Piper
pertenecen a la misma síntesis PCM; se comprueban contra el WAV original antes de
usarlas. Se aborta ante símbolos sin mapear, duraciones incompletas o PCM distinto.

48 entradas cada ~10 ms: 36 señales acústicas/temporales, nueve indicadores de
forma fonética y tres señales de tiempo transcurrido/restante y duración del
fonema. Son duraciones internas del sintetizador, no fronteras humanas verificadas.
No es un reconocedor nuevo de fonemas ni una nueva voz: aprende formas de boca
condicionadas por el audio y las marcas del Piper existente.

Entrenamiento temporal con contexto, balance .5 y peso máximo 4; consejo peso 1,
saludo/despedida .25. Ocho candidatos prefijados por idioma, elegidos sólo en dev.
ES: no lineal escala .5, ridge 100, transición 0. EN: no lineal escala .5,
ridge 1, transición .05. Archivos `hybrid-es.json` y `hybrid-en.json` bajo
`tmp/isa-own-classifier/hybrid-phonetic-v1/`. El nombre v9 es la clave del visor;
v8 sigue identificando las reglas fonéticas sin entrenar.

## Resultado sobre los mismos 32 audios test regenerados

Se mide sólo el consejo, sin inflar con los saludos repetidos. La referencia es
Rhubarb sin revisión humana: concordancia, no porcentaje de calidad visual.

| Variante | ES concordancia | ES F1 macro | EN concordancia | EN F1 macro |
| --- | ---: | ---: | ---: | ---: |
| V7 congelado | 58,16 % | 35,21 % | 59,35 % | 50,11 % |
| Reglas fonéticas sin entrenar | 25,67 % | 15,31 % | 44,18 % | 32,16 % |
| Híbrido entrenado | 56,38 % | 33,94 % | 59,53 % | 49,69 % |

El híbrido supera las reglas fonéticas simples, pero no supera consistentemente
V7. No se promovió ni se reajustó con los resultados test.

Las cifras V7 difieren del informe anterior porque estos son renders nuevos y
sus propias etiquetas Rhubarb; todas las filas aquí comparten exactamente PCM.

## Cierres y pausas, métricas separadas

Ventanas de consejo donde el modelo cierra A/X y la referencia pide apertura:
ES V7 6,49 % -> híbrido 7,05 %; EN V7 7,77 % -> híbrido 5,70 %.
Denominador: todas las ventanas del consejo, no sólo las ventanas abiertas.

Boca cerrada en pausas insertadas conocidas: ES 84,08 % -> 83,30 %;
EN 99,61 % -> 99,42 %. Tampoco hay mejora global de pausas.

En el ejemplo inglés a 3,151 s, reglas, V7 e híbrido siguen solicitando X. El
entrenamiento no demuestra haber corregido ese caso señalado por el usuario.
Hace falta escuchar y anotar la frontera real; más generaciones con las mismas
etiquetas débiles no garantizan corregirla.

## Prueba visual y validación

`tmp/isa-own-classifier/hybrid-animation-v1/index.html`: mismo audio de la demo
anterior, V7 + tiempos como control inicial y el híbrido entrenado a la derecha.
Se puede elegir también la regla fonética o V7. Conserva energía, pausas,
desfases, apertura/cierre, aceleración de cierres y perfiles ES/EN independientes.
No se añadieron imágenes ni se cambiaron los modelos Piper originales.

Pasaron 56 pruebas Python, pruebas del planificador y comprobaciones Playwright
de ambas voces, cambio entre los tres métodos sin reiniciar audio, identidad de
planes cuando ambos usan V7, búsqueda temporal, ajustes/exportación, móvil sin
desbordamiento y ausencia de peticiones externas. Esto verifica funcionamiento,
no una evaluación humana de la sincronización.

Producción y modelos anteriores se conservan. El siguiente paso útil es anotar
fronteras de habla/pausa y cierres sobre unas frases reales, evaluar errores en
milisegundos y mejorar coarticulación antes de ampliar automáticamente el corpus.

## Reproducción

```powershell
.\tmp\isa-phoneme-env\Scripts\python.exe -X utf8 experiments/isa_classifier/generate_phonetic_corpus.py --source tmp/isa-own-classifier/corpus-v7/corpus.json --output tmp/isa-own-classifier/corpus-phonetic-nuevo
python experiments/isa_classifier/train_phonetic.py --corpus tmp/isa-own-classifier/corpus-phonetic-nuevo/corpus.json --baseline tmp/isa-own-classifier/v7 --output tmp/isa-own-classifier/hybrid-nuevo
```

Usar carpetas nuevas para otros renders. Los artefactos completos de esta ronda
incluyen `corpus-phonetic-v1/corpus.json` y `hybrid-phonetic-v1/evaluation.json`.
