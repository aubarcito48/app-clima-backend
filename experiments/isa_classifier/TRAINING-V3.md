# Entrenamiento V3 · 16/11/2026

Se generaron y procesaron **20 grabaciones locales nuevas**, 95,10 segundos en
total, con Sharvard/es y Cori/en. El plan de frases y particiones está versionado
en `corpus_plan.json`. Los WAV, modelos y métricas completas están en `tmp/` y no
se publican ni se cargan desde Django.

## Separación de datos

Por idioma: seis grabaciones para entrenar, dos para elegir configuración y
dos para la evaluación final. Las frases son distintas y se comprueban hashes
de PCM para rechazar copias del mismo audio entre conjuntos. Los conjuntos se
fijaron antes de sintetizar. Las ventanas vecinas de un mismo archivo se mantienen
juntas; el contexto temporal no cruza de una grabación a otra.

Se probaron doce configuraciones prefijadas. La selección usa sólo el recall
equilibrado medio por grabación en desarrollo, con concordancia como desempate.
No se reentrenó usando desarrollo o prueba después de elegir. El conjunto final
ya fue observado: cambios posteriores necesitan una nueva evaluación reservada.

Las etiquetas siguen siendo **débiles, generadas por Rhubarb**, sin revisión
humana. Por lo tanto, los resultados miden concordancia con esa referencia,
no precisión visual, fonética real ni satisfacción del usuario.

## Resultado sobre las cuatro grabaciones finales

Promedios por grabación, dando el mismo peso a cada una:

| Modelo / referencia | Español: concordancia | Inglés: concordancia |
| --- | ---: | ---: |
| Centroides V1 entrenados con este mismo corpus | 25,2 % | 33,4 % |
| Elegir siempre la clase más frecuente del entrenamiento | 40,4 % | 39,5 % |
| **Modelo temporal V3** | **53,9 %** | **60,0 %** |

| Recall equilibrado medio por grabación | Español | Inglés |
| --- | ---: | ---: |
| Centroides con este mismo corpus | 25,0 % | 30,8 % |
| Clase mayoritaria | 16,3 % | 12,5 % |
| **Modelo temporal V3** | **39,3 %** | **41,2 %** |

Los porcentajes V1 iniciales de 46,5 % y 37,4 % correspondían a otras grabaciones
y otro entrenamiento. No son una comparación directa con este nuevo resultado.
La tabla compara ambos modelos sobre exactamente los mismos archivos finales.

## Cambio de modelo

`temporal.py` implementa regresión lineal regularizada con objetivos por clase,
pesos de balance y contexto de ventanas a ±20/40 ms. La normalización se aprende
sólo del entrenamiento. Opcionalmente decodifica la secuencia completa con
transiciones aprendidas sin incluir fronteras entre archivos.

- Español: regularización 1, balance 0,5 y sin decodificación por transiciones,
  elegidos en desarrollo. El contexto ya participa en cada predicción.
- Inglés: regularización 100, balance 0,5 y fuerza de transiciones 0,15.
- Se guardan JSON, no objetos ejecutables ni archivos pickle.
- Inferencia recibe sólo características del audio; no consulta marcas Rhubarb
  ni texto. `predict_audio.py` admite tanto V1 como V3 según versión del modelo.
- Modelos de aproximadamente 47 KB por idioma. La medición local de decodificación
  del conjunto final fue ~2 ms/es y ~6 ms/en, **excluyendo** lectura, características,
  síntesis y generación de etiquetas. No es una medición de latencia en Render.

## Verificaciones y límites

Pasaron veinte pruebas sintéticas/de integración: contexto en bordes, ausencia
de transiciones entre archivos, rechazo de datos inválidos, persistencia JSON,
revisión humana y separación de conjuntos. Las cuatro líneas de tiempo generadas
también pasaron el validador actual de marcas del backend, sin integrarlas al
endpoint ni cambiar producción.

Hay ejemplos de las nueve formas en ambos entrenamientos. La cobertura todavía
es muy desigual: español sólo tiene 39 ventanas D, 37 E y 38 H, frente a 1060 B.
Son ventanas superpuestas, no observaciones independientes. Falta ampliar esos
casos y revisar cierres, silencios y fronteras con el editor acústico.

Dos grabaciones finales por idioma son insuficientes para generalizar. No se
validó calidad de animación, ojos, parpadeos, expresiones, consumo máximo de memoria
ni comportamiento en el servidor de producción. El modelo continúa experimental.

## Reproducir

Desde la raíz del backend; para generar audio se necesita el entorno local de
Piper y Rhubarb ya configurado. Ninguno de los comandos usa Groq u OpenWeather:

```powershell
.venv/Scripts/python.exe experiments/isa_classifier/generate_corpus.py --output tmp/isa-own-classifier/corpus-v3
python experiments/isa_classifier/train_temporal.py --corpus tmp/isa-own-classifier/corpus-v3/corpus.json --output tmp/isa-own-classifier/v3
python -m unittest discover -s experiments/isa_classifier -p test_*.py -v
python experiments/isa_classifier/predict_audio.py --model tmp/isa-own-classifier/v3/audio-en.json --wav tmp/isa-own-classifier/corpus-v3/en-test-01.wav --output tmp/isa-own-classifier/v3/inference-en.json
```

El generador permite retomar archivos ya creados y rechaza cambios del plan o
del PCM registrado. La reproducción exacta de la síntesis puede depender de las
versiones y los modelos locales; el manifiesto guarda el PCM obtenido realmente.
