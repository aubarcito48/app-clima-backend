# Prueba fonética de Piper (local)

Objetivo: probar información fonética explícita antes de aumentar el banco visual.
No reentrena V7 ni cambia la aplicación publicada. `v8` es sólo la clave de la
condición experimental en los visores; no representa un clasificador V8 entrenado.

## Qué se obtiene

- Cori y Sharvard exponen duraciones por ID desde el mismo pase que genera el audio.
- El grafo ONNX se modifica sólo en memoria. Se verifica SHA-256 del archivo de voz
  antes y después. Dependencia ONNX aislada en `tmp/isa-phoneme-env`; sin cambios
  a los requisitos ni al entorno de producción.
- Se agrupan correctamente BOS, PAD, fonemas de varios IDs y EOS. La suma de las
  duraciones debe coincidir exactamente con el número de muestras PCM o se aborta.
- Mapeos IPA a los visemas existentes, con perfiles ES/EN. Símbolos desconocidos
  provocan error; nunca se silencian inadvertidamente.
- Acentos, marcas de longitud y separadores de palabras no se convierten en
  silencio. Las pausas insertadas conservan su duración y la boca de reposo.
- Los diptongos agrupados pasan por dos articulaciones. Su frontera interna es
  una división estimada a la mitad; Piper entrega sólo la duración del conjunto.

## Comparación

`tmp/isa-own-classifier/phoneme-v1/index.html`: Rhubarb frente a fonética Piper
o V7 seleccionable, mismo PCM, mismo selector y mismas imágenes en cada idioma.
Dos frases cortas con saludo y despedida de la app. No se utilizan para entrenar.

`tmp/isa-own-classifier/phoneme-timing-v1/index.html`: las nuevas marcas alimentan
el planificador temporal experimental. Incluye fonema activo y forma solicitada,
onda de audio, controles independientes ES/EN y detección de cierres largos.
Esta comparación cambia también el planificador, por lo que no aísla por sí sola
la contribución de la fonética. Para aislarla, usar el primer visor.

`tmp/isa-own-classifier/phoneme-integrated-v1/index.html`: comparación completa.
Por defecto, V7 + planificador temporal a la izquierda y fonemas Piper + el mismo
planificador a la derecha. Conserva onda, pausas conocidas/candidatas, ritmo,
desfase, apertura/cierre, aceleración y perfiles independientes ES/EN. Permite
seleccionar V7 también a la derecha: con los mismos ajustes los planes deben
coincidir. Cambiar las marcas no reinicia ni sustituye el audio.
Las dos alternativas se comparan; no hay fusión ni reentrenamiento del modelo V7.
Para generarlo, usar `analyze_timing.py --integrated` antes de `build_timing_lab.mjs`.

Importante: el selector español actual conserva ciclos completos; en estas dos
condiciones del primer visor selecciona los mismos frames, aunque cambien las
marcas. El laboratorio temporal permite explorar esa limitación sin tocarlo.

## Límites

Las duraciones son predicciones internas del sintetizador, no anotaciones humanas.
El mapeo de visemas es una regla articulatoria inicial, no un modelo nuevo entrenado.
Las referencias Rhubarb tampoco son verdad absoluta. Dos muestras no permiten
afirmar una mejora porcentual, generalización, ni suficiencia de todas las imágenes.
Faltan revisión visual, coarticulación más precisa y evaluación con frases
reservadas y anotadas manualmente antes de decidir una integración.

Las letras A–H/X identifican formas de boca compatibles con el banco actual; no
son letras del texto hablado. Referencia de las formas:
https://github.com/DanielSWolf/rhubarb-lip-sync#mouth-shapes

## Reproducir

Desde la raíz del backend:

```powershell
.\tmp\isa-phoneme-env\Scripts\python.exe -X utf8 experiments/isa_classifier/probe_phonetic.py --output tmp/isa-own-classifier/phoneme-nuevo
node experiments/isa_classifier/build_animation_demo.mjs ../app-clima tmp/isa-own-classifier/phoneme-nuevo
python experiments/isa_classifier/analyze_timing.py --demo tmp/isa-own-classifier/phoneme-nuevo --output tmp/isa-own-classifier/phoneme-timing-nuevo
node experiments/isa_classifier/build_timing_lab.mjs ../app-clima tmp/isa-own-classifier/phoneme-timing-nuevo
```

Usar otra carpeta para nuevas generaciones: la inferencia contiene aleatoriedad.
