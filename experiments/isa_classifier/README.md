# Clasificador propio de Isa · primer prototipo local

Correcciones funcionales: [recuperación, cierre y reintentos de voz](FUNCTIONALITY-FIXES-V1.md).

Nuevo entrenamiento [Random Forest V2](TRAINING-FOREST-REVIEW-V2.md): 48 consejos
nuevos, 92 audios aceptados, evaluación final separada y comparación con V1.
Mejora acústica modesta; candidato local, sin sustitución automática.

Nueva [prueba integrada antes de entrenar](FUNCTIONALITY-REVIEW-V1.md): seis
muestras ES/EN con audio común, renderizadores anterior/corregido, barras y
prueba interactiva de recuperación de imágenes. RF congelado.

Auditoría de 25 funciones con las cuatro skills: [resultados y prioridades](FUNCTIONALITY-AUDIT.md).
Incluye recuperación de recursos, salida al reposo, resolución temporal y pruebas
de ciclo de vida. Evidencias en `tmp/isa-own-classifier/functionality-audit-v1/index.html`.

Primera corrección posterior al relevamiento: [etiquetas visuales y empalme EN](VISUAL-POLICY-V1.md).
Comparación con RF/audio idénticos en
`tmp/isa-own-classifier/visual-policy-review-v1/index.html`. Apertura/cierre
mejoran en la muestra; empalme candidato opcional. No se reentrena ni despliega.

Relevamiento de voz y animación con las cuatro skills:
[hallazgos y prioridades](SKILLS-AUDIT.md). Evidencia local en
`tmp/isa-own-classifier/skills-audit-v1/index.html`. No cambia producción.

Última prueba: [red temporal pequeña y referencias de pausas](TRAINING-NEURAL-TEMPORAL.md).
No superó a los árboles en consejos nuevos; incluye comparación visual con el
mismo audio y auditoría de continuidad. Producción permanece sin cambios.

Comparación más reciente: [Random Forest frente a XGBoost](TRAINING-FOREST.md).
Vista simultánea con el mismo audio y barras:
`tmp/isa-own-classifier/forest-direct-v1/index.html`.

Estado: **experimental, no apto para reemplazar Rhubarb**. No está importado por
Django, no modifica Piper, los selectores existentes ni los recursos publicados.
No cambia configuración, dependencias de producción ni rutas HTTP. No usa red.

Actualización: se entrenó el modelo temporal V3 con veinte grabaciones nuevas.
Superó a los centroides y a la clase mayoritaria sobre sus grabaciones finales
reservadas. Ver [resultados y límites del entrenamiento V3](TRAINING-V3.md).
Los resultados V1 de abajo se conservan como registro del primer experimento.

La ronda siguiente comparó cinco niveles de balanceo en frases nuevas. V4 no
superó al modelo V3 congelado en F1 macro de prueba: ver [balanceo V4](BALANCE-V4.md).
Se conserva V3 como referencia experimental, sin integración en producción.

Ya hay una [prueba conjunta de voz y animación](ANIMATION-DEMO.md), con comparación
Rhubarb/propio en ambos idiomas y una selección de sólo 24 candidatos de otras
dos tomas, separados de la animación hasta revisar su utilidad.

La [ronda V5](TRAINING-V5.md) amplió el corpus a cuarenta audios y comparó una
variante no lineal. Hay una nueva prueba visual en
`tmp/isa-own-classifier/animation-v5/index.html` que conserva el audio del ensayo
anterior y permite alternar V5/V3. Los resultados fueron mixtos por idioma y métrica.

La [ronda V6](TRAINING-V6.md) agrega 48 consejos breves nuevos con el saludo y
despedida exactos de la app. La métrica principal excluye las frases repetidas.
Abrir `tmp/isa-own-classifier/animation-v6/index.html` para la prueba actual,
conservando las anteriores como referencia.

La etapa actual es el [laboratorio de ritmo, pausas y boca](TIMING-LAB.md):
`tmp/isa-own-classifier/timing-v1/index.html`. Permite comparar el selector actual
con ajustes temporales experimentales por idioma, sin otra ronda de entrenamiento.

La corrección más reciente es [aceleración local de cierres V2](CLOSURE-TIMING-V2.md),
en `tmp/isa-own-classifier/timing-v2/index.html`: conserva el banco y acorta
un cierre visual prolongado del caso inglés señalado por el usuario.

La [ronda V7](TRAINING-V7.md) amplió el corpus a 128 grabaciones y la prueba final
a 32 consejos nuevos. Español ganó con canales temporales; inglés con más datos
y señales originales. La prueba actual está en `tmp/isa-own-classifier/timing-v3/index.html`
y la comparación de modelos en `tmp/isa-own-classifier/animation-v7/index.html`.

## Qué está implementado

- Audio: características espectrales de ventanas de 40 ms cada ~10 ms,
  normalización aprendida, clasificación por centroides y suavizado temporal.
  Entrena dos modelos independientes: Sharvard/es y Cori/en. Inferencia desde
  PCM sin consultar etiquetas, transcripciones ni ejecutar Rhubarb.
- Imagen: recorte de boca, descriptores de color y gradiente, centroides por
  idioma. Genera propuestas para los 204 frames de cada atlas y páginas HTML
  para corregirlas y exportar etiquetas revisadas. `--labels` permite volver a
  entrenar con esa revisión humana en lugar de las etiquetas provisionales.
- Usa los códigos A–H/X para compatibilidad con los selectores actuales;
  **no son letras del texto ni un nuevo alfabeto fonético**.
- Conserva índice del atlas y frame de origen por separado: el video tiene un
  recorte inicial. Las etiquetas revisadas usan el índice del atlas.
- Cuarenta y ocho pruebas Python, verificaciones Node del planificador y chequeos de navegador.

Los algoritmos son nuestros, pero NumPy/Pillow siguen siendo dependencias de
código abierto. La primera supervisión acústica proviene de marcas Rhubarb
guardadas y la visual de anotaciones anteriores, algunas provisionales. Esto
es un arranque con etiquetas débiles, no entrenamiento desde cero con datos
humanos ni prueba de superioridad respecto del sistema anterior.

## Resultado inicial · 16/11/2026

Entrenamiento: un WAV largo por idioma. Evaluación: otra grabación completa,
las muestras de grados. No se mezclan ventanas de un mismo archivo entre
entrenamiento y evaluación. Se rechazan duplicados de PCM aunque cambien sus
metadatos; frases coincidentes, otras tomas y cercanía temporal requieren
revisión manual adicional.

| Muestra reservada | Concordancia con Rhubarb | Recall equilibrado | Referencia trivial: clase más frecuente del entrenamiento |
| --- | ---: | ---: | ---: |
| Español, grados-es.wav | 46,5 % | 43,7 % | 49,4 % |
| Inglés, degrees-en.wav | 37,4 % | 31,1 % | 66,5 % |

**El prototipo pierde contra la referencia trivial en estas muestras.** No debe
habilitarse en producción. Falta la forma D en el entrenamiento español.
Las cifras miden concordancia por ventana con etiquetas automáticas, no calidad
visual, precisión fonética real ni percepción del usuario. No se publica una
precisión de imagen: las mismas etiquetas débiles usadas para ajustar el modelo
no pueden emplearse para validarlo. El margen entre centroides no es probabilidad.

El recorte de boca fue inspeccionado en los dos idiomas. Este clasificador
todavía **no predice ojos, parpadeos, cejas o expresiones**. El editor permite
anotar ojos abiertos/entreabiertos/cerrados, expresión y dirección de la cabeza
en `attributes`, separados de las etiquetas de boca. Un parpadeo exige analizar
la secuencia de ojos, no sólo un frame cerrado. La continuidad del
rostro/cuerpo sigue en los selectores de frames completos existentes. Separar
esas tareas evita confundir una buena forma de boca con una buena transición.

## Ejecución desde app-clima-backend

Usar un entorno experimental separado si el Python local no tiene NumPy y
Pillow. No instalar estas dependencias en Render para este experimento:

```powershell
python -m venv tmp/isa-classifier-env
tmp/isa-classifier-env/Scripts/python.exe -m pip install -r experiments/isa_classifier/requirements.txt
```

En los ejemplos siguientes, `python` representa ese intérprete o uno local con
esas dependencias. Los WAV de prueba actuales están en `tmp/`, ignorados por
Git; un clon nuevo necesita grabaciones locales equivalentes con marcas `isav`.
Los modelos y páginas generados también quedan ignorados en `tmp/`.

```powershell
python -m unittest discover -s experiments/isa_classifier -p test_classifier.py -v
python experiments/isa_classifier/run_audio.py --train es:tmp/isa-rhubarb/es_long.wav --train en:tmp/isa-rhubarb/en_long.wav --test es:tmp/isa-pronunciation/grados-es.wav --test en:tmp/isa-pronunciation/degrees-en.wav --output tmp/isa-own-classifier/v1
python experiments/isa_classifier/predict_audio.py --model tmp/isa-own-classifier/v1/audio-en.json --wav tmp/isa-pronunciation/degrees-en.wav --output tmp/isa-own-classifier/v1/inference-en.json
python experiments/isa_classifier/review_images.py --frontend ../app-clima --language en --output tmp/isa-own-classifier/v1
python experiments/isa_classifier/review_images.py --frontend ../app-clima --language es --output tmp/isa-own-classifier/v1
node experiments/isa_classifier/check_review.mjs ../app-clima tmp/isa-own-classifier/v1
```

Abrir `review-es.html` y `review-en.html` directamente en el navegador. Las
selecciones no se guardan automáticamente: descargar las etiquetas antes de
cerrar. Ninguna propuesta se exporta como revisada sin elegirla manualmente.
El chequeo de navegador usa una selección sintética que descarta, no genera
anotaciones humanas. Para entrenar con una exportación real:

```powershell
python experiments/isa_classifier/review_images.py --frontend ../app-clima --language en --labels tmp/isa-labels-en.json --output tmp/isa-own-classifier/reviewed
```

## Segunda etapa: supervisión acústica propia

`review_audio.py` genera un editor autónomo con audio, forma de onda, reproducción
lenta, escucha de cada tramo y edición de límites. Se pueden dividir/unir marcas,
guardar una revisión incompleta y reimportarla. Todo comienza **sin revisar**.
El botón de exportación para entrenar exige confirmar cada intervalo. No hay
botón de aprobación masiva. Un WAV sin `isav` también se puede anotar desde cero.

```powershell
python experiments/isa_classifier/review_audio.py --wav tmp/isa-pronunciation/degrees-en.wav --language en --output tmp/isa-own-classifier/v2/audio-review-en.html
python experiments/isa_classifier/review_audio.py --wav tmp/isa-pronunciation/grados-es.wav --language es --output tmp/isa-own-classifier/v2/audio-review-es.html
node experiments/isa_classifier/check_audio_review.mjs ../app-clima tmp/isa-own-classifier/v2
```

Cada JSON exportado queda vinculado al SHA-256 del PCM y su frecuencia de muestreo,
idioma y versión. Cambiarlo de nombre no permite aplicarlo a otra grabación.
`annotations.py` rechaza revisiones parciales, huecos, superposiciones, duraciones
distintas, etiquetas inválidas y cambios de identidad. El formulario comprueba
también esa identidad al retomar una revisión.

Guardar las exportaciones finales en una carpeta local de anotaciones con el
nombre del WAV: `es_long.json`, `en_long.json`, `grados-es.json`, `degrees-en.json`.
Para exigir supervisión propia en **entrenamiento y evaluación**:

```powershell
python experiments/isa_classifier/run_audio.py --train es:tmp/isa-rhubarb/es_long.wav --train en:tmp/isa-rhubarb/en_long.wav --test es:tmp/isa-pronunciation/grados-es.wav --test en:tmp/isa-pronunciation/degrees-en.wav --annotations-dir tmp/isa-own-classifier/annotations --require-reviewed --output tmp/isa-own-classifier/reviewed-audio
```

Si falta cualquier anotación, el comando se detiene; no reemplaza esa revisión
por Rhubarb silenciosamente. El informe conserva la procedencia de cada archivo.
Sin `--require-reviewed` sigue siendo posible reproducir la referencia débil de
la primera etapa. Los resultados iniciales de arriba no han mejorado por agregar
el editor: todavía no hay un corpus humano real revisado y reentrenado.

Los chequeos del navegador seleccionan valores sintéticos para probar exportación
y restauración y luego los descartan. **No cuentan como anotaciones reales**.

El JSON de inferencia es un artefacto experimental. No se inyecta en WAV de
producción ni cumple aún todos los límites de admisión del endpoint. Audios muy
cortados podrían producir demasiadas marcas; hay que verificarlo antes de
integrar cualquier motor nuevo.

## Trabajo siguiente para una sustitución real

Primera etapa de calidad de etiquetas completada: [PAUSE-LABEL-REPAIR.md](PAUSE-LABEL-REPAIR.md).
Se corrigieron interiores de pausas insertadas con PCM cero, conservando originales;
el habla queda estable y el selector visual mantiene limitaciones independientes.

Clasificador de árboles potenciados y decodificación temporal, con evaluación
acústica y 124 planes visuales: [TRAINING-BOOSTED.md](TRAINING-BOOSTED.md).
Sube la concordancia española, pero no supera todos los controles de pausa/animación.

Nueva variante con identidad de fonemas individuales: [TRAINING-IDENTITY.md](TRAINING-IDENTITY.md).
Mantiene todas las automatizaciones del visor. Hay mejoras y regresiones; no se promovió.

Ronda de 231 grabaciones con contenido variado, reducción automática de velocidad
y balanceo: [TRAINING-RATE-BALANCE.md](TRAINING-RATE-BALANCE.md). Incluye visor
completo con barras, dos ritmos y clasificadores anterior/nuevo seleccionables.

Prueba de reducción automática de velocidad por frase en ambos idiomas, con
regeneración de voz/fonemas/animación: [AUTOMATIC-VOICE-RATE.md](AUTOMATIC-VOICE-RATE.md).

Se probó calibración automática de los avances de animación en inglés:
[TIMING-POLICY-V1.md](TIMING-POLICY-V1.md). La validación conservó el perfil actual;
no se atribuye una mejora a esta búsqueda de parámetros.

Se completó la primera ronda híbrida entrenada: resultados y limitaciones en
[TRAINING-PHONETIC-V1.md](TRAINING-PHONETIC-V1.md). No superó consistentemente V7.

La prueba local de fonemas y duraciones internas de Piper está descrita en
[PHONETIC-V1.md](PHONETIC-V1.md). Conserva el banco visual y compara con V7;
no constituye un reentrenamiento ni una integración en producción.

1. Revisar formas de boca, cubrir clases ausentes y separar frames de evaluación
   por toma/secuencia, evitando vecinos casi idénticos entre conjuntos.
2. Crear un corpus balanceado de ambas voces con frases, pausas y velocidades
   distintas. Anotar y corregir fronteras de audio usando el editor y el formato
   humano ya implementados; aún faltan esas anotaciones reales.
3. Evaluar un modelo temporal con contexto fonético; la forma de boca no puede
   deducirse con suficiente precisión de volumen o una ventana espectral sola.
4. Incorporar etiquetas separadas de ojos/parpadeo, expresión y pose; validar
   visualmente transiciones además de métricas por clase y errores en milisegundos.
5. Comparar lado a lado en las pruebas de Isa, medir memoria y latencia en el
   entorno objetivo y recién entonces proponer integración por idioma con fallback.
