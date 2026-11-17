# Prueba conjunta y selección reducida de frames · 16/11/2026

## Abrir la prueba

Desde el backend, abrir en un navegador:

`tmp/isa-own-classifier/animation-ab/index.html`

Es un HTML autónomo con audio y atlas embebidos. No requiere servidor, API ni
conexión a Internet. Permite alternar español/Sharvard e inglés/Cori, V3/V4,
tema, velocidad y posición del audio. «Reproducir desde el inicio» inicia ambas
animaciones con un único reloj y una única reproducción de voz.

Izquierda: marcas Rhubarb. Derecha: predicción acústica propia. Ambos lados usan
el **mismo PCM**, el mismo selector actual por idioma y el mismo banco de frames.
Sólo cambian las marcas acústicas; no se cambian video, voz, texto ni ritmo entre
lados. Se verifica que sustituir `isav` no modifique el PCM ni deje metadata
duplicada. Se conservan metadatos de actuación existentes en el WAV, aunque esta
comparación controla la boca y mantiene la pose despierta en ambos retratos.

El texto español dura 5,370 s; el inglés 5,706 s. Son frases nuevas sólo para
revisión visual, nunca se agregan a entrenamiento ni se usan para elegir modelo.
V3 sigue siendo la referencia propia y V4 un candidato experimental.

Esto muestra **frames completos con ojos, rostro y cuerpo**, utilizando el
renderizador actual. No usa un recorte de boca pegado sobre un retrato inmóvil.
No demuestra que ojos/expresiones estén reconocidos por un nuevo modelo: esos
movimientos pertenecen al material visual existente.

## Qué material adicional se usó

El prototipo visual inicial sólo había usado los atlas actuales de español e
inglés. El entrenamiento acústico sólo había usado WAV: no las otras tomas.

Ahora se analizaron las tomas `isa-hablando2-video.mp4` y
`isa-hablando3-video.mp4`. Se verificó el SHA-256 de cada video contra su caché
de extracción existente; no se reextrajeron cientos de imágenes nuevas.
Videos de guía y grabaciones de pruebas no se incorporan automáticamente como
si fueran nuevas tomas limpias del personaje.

De 480 frames cacheados, se excluyeron los tramos inicial/final de reposo y se
analizaron 432. Sólo se exportaron **24 candidatos**, como máximo doce por toma.
Quedan en `extra-frames.html`, enlazado desde la prueba conjunta.

Criterios: novedad de boca respecto del banco actual y los candidatos ya elegidos,
prioridad a formas provisionales poco representadas, distancia aproximada de pose
no mayor a 0,10 y separación de al menos seis frames dentro de la misma toma.
Se descartan casi duplicados con novedad inferior a 0,015. Las distancias son
descriptores heurísticos normalizados, no probabilidad ni medida perceptual validada.

Distribución propuesta: 5 D, 6 F, 4 C, 4 X, 3 E y 2 B. El modelo visual de arranque
sólo conoce estas seis clases; no puede garantizar nuevas muestras G/H.
Las propuestas visibles incluyen errores posibles —por ejemplo, sonrisas y cierres
pueden confundirse— y **ninguna está marcada como revisada**.

Estos 24 frames se guardan aparte. No se mezclan en la animación A/B todavía:
cambiar banco y clasificador simultáneamente impediría atribuir las diferencias.
Primero se deben revisar las formas reales y las transiciones de entrada/salida;
una pose aproximadamente parecida no garantiza continuidad de ojos o cabeza.

Más frames pueden ampliar la variedad visual. No mejoran automáticamente el
reconocimiento del audio: harían falta pares de audio/imagen con tiempos y formas
verificados. No se considera que estas tomas estén alineadas con Cori/Sharvard.

## Comprobaciones

- 29 pruebas sintéticas/de integración aprobadas.
- Navegador: ES/EN × V3/V4, ambos retratos activos, audio avanzando, pausa,
  búsqueda de instante, cambio de velocidad, tema y ancho de 390 px.
- Se inspeccionaron capturas de la animación y la selección de frames.
- Cero peticiones HTTP externas durante la prueba de navegador.
- Las dos predicciones por idioma pasan el validador de tiempos actual.
- El diagnóstico registra diferencias reales en los frames elegidos entre ambos
  lados. Ese número **no mide precisión**: sólo descarta una comparación que
  accidentalmente reproduzca exactamente el mismo plan en ambos paneles.
- Los archivos runtime del frontend, los videos y producción permanecen intactos.

## Reproducir

Desde la raíz del backend, con los modelos y cachés de las pruebas anteriores:

```powershell
.venv/Scripts/python.exe experiments/isa_classifier/prepare_demo.py --output tmp/isa-own-classifier/animation-ab
python experiments/isa_classifier/select_extra_frames.py --frontend ../app-clima --model tmp/isa-own-classifier/v1/image-es.json --output tmp/isa-own-classifier/animation-ab --limit 24
node experiments/isa_classifier/build_animation_demo.mjs ../app-clima tmp/isa-own-classifier/animation-ab
node experiments/isa_classifier/check_animation_demo.mjs ../app-clima tmp/isa-own-classifier/animation-ab
python -m unittest discover -s experiments/isa_classifier -p test_*.py -v
```

Los HTML, audios, candidatos y capturas están bajo `tmp/` ignorado por Git. No se
hicieron commit, push ni despliegue de esta etapa.
