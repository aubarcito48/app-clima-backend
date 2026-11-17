# Relevamiento de Isa con las cuatro skills · 17 de noviembre de 2026

La base está funcionando, pero el límite principal observado está en las
referencias visuales y en cómo el selector recorre el banco de frames. La voz
no presenta saturación en esta muestra. No conviene otra ronda de entrenamiento
idéntica antes de corregir y evaluar esas dos partes.

## Alcance y evidencia

- Audio Lens: 32 WAV finales de la ronda TDNN, 16 consejos diferentes en dos
  velocidades, con verificación de la identidad PCM; ocho espectrogramas.
- Prosody Lens: ocho informes (dos consejos por idioma, original/automático),
  con el texto exacto y salida JSON, Markdown y HTML. Análisis local con pitch
  por autocorrelación, sin Praat ni alineador independiente de palabras.
- Image Eye Checker: 408 frames extraídos de los atlas existentes, 204 ES y
  204 EN. La detección encuentra rostro en todos; esto no equivale a validar
  los puntos o las expresiones con 100 % de precisión.
- Animator's Survival Kit: revisión de tiempos, continuidad, poses de entrada/
  salida, movimiento secundario y bocas legibles, aplicada a las secuencias
  y a contactos visuales. No se trasladan reglas genéricas de anticipación
  como un adelanto global del audio.
- Se reconstruyen 64 planes finales, 32 RF y 32 TDNN, con los parámetros
  existentes. Se reutiliza además la auditoría de 128 planes con/sin aceleración.

Artefacto de entrada visual: `neural-visual-v1/visual-batch.json`; audio:
`corpus-tdnn-v1/corpus.json`, bajo `tmp/isa-own-classifier/`. No es una auditoría
del servicio desplegado ni una medición de rendimiento de Render.

## Lo que está bien

**Audio limpio en las muestras.** Cero muestras recortadas por saturación en
32 WAV. Picos entre -6,63 y -4,67 dBFS ES, y -5,56 y -4,08 EN. RMS aproximado
entre -21,16 y -20,21 dBFS ES, y -22,59 y -21,51 EN. No hay evidencia aquí para
subir volumen o normalizar de nuevo; estas métricas no prueban pronunciación
perfecta ni equivalen a LUFS o evaluación auditiva humana.

**Ritmo independiente por idioma.** La reducción de velocidad regenera audio y
fonemas; el reproductor permanece en 1×. El saludo y la despedida se conservan.
La aceleración local inglesa reduce el indicador de cierre visual prolongado
en los 16 audios evaluados para cada modelo. El reloj no acumula retrasos.

**Base facial aprovechable.** El detector no señala desenfoque ni exposición
problemática en los 408 frames. Encuentra 12 frames con ojos cerrados por idioma,
agrupados en tramos de aproximadamente 83–167 ms ES y 167 ms EN, compatibles
visualmente con parpadeos. No hay motivo medido para eliminarlos ni rehacer
ojos/expresiones. Estos umbrales proceden de un detector para fotografías.

## Hallazgos prioritarios

### 1. El catálogo visual contiene referencias inconsistentes

En ES sólo hay 51 anclas para 204 frames. `labelsFor` propaga la etiqueta del
ancla más cercana. Así, el frame de atlas ES #51 recibe X del ancla #52, aunque
en el contacto se ve la boca abierta; ES #86 también recibe X aunque muestra
separación visible. En EN el catálogo es denso, pero siguen existiendo casos
para revisar: #43 figura X y muestra apertura; #66/#67/#68 tienen etiquetas
de habla con labios visualmente casi juntos. No se decide todo su visema por
un único valor de apertura mandibular.

Las láminas `frame-contact-es.png` y `frame-contact-en.png` muestran esos casos.
Los números son índices del atlas, no los números del video original; ambos
quedan registrados en `frame-index.json`.

**Optimización propuesta:** revisar primero apertura/reposo y fronteras de
transición por frame, después formas finas. Mantener confianza y procedencia de
cada etiqueta. No convertir automáticamente `jaw_open` en verdad de entrenamiento.
La mandíbula es útil para encontrar candidatos; labios, dientes y contexto
también importan. Conservar todas las imágenes y cambiar sólo sidecars de prueba.

### 2. La forma solicitada no siempre está disponible cerca del instante

El planificador avanza sobre un ciclo fijo, con deriva máxima de cuatro frames
ES y seis EN. Aunque el clasificador pida la boca correcta, no puede saltar a
cualquier otra boca del banco sin arriesgar la pose y el movimiento.

Sobre los instantes del consejo donde RF pide una forma distinta de reposo,
la forma aparece en la ventana permitida en **62,31 % ES (1.450/2.327)** y
**71,86 % EN (1.348/1.876)**. Es una disponibilidad optimista por instante:
ignora las restricciones de conexión entre instantes y depende de etiquetas
visuales aún provisionales. **No es la precisión del clasificador ni un límite
demostrado del aprendizaje.** Describe una restricción del selector actual.

**Optimización propuesta:** después de revisar etiquetas, comparar un selector
de secuencias cortas con más de una continuación posible, compatible en pose,
dirección y velocidad del movimiento. Priorizar mandíbula/apertura y visemas
legibles. No ampliar la deriva sin controles ni aumentar la velocidad global.
Medir coincidencia visual, cierres y continuidad por separado.

### 3. El empalme del ciclo inglés merece una corrección específica

La repetición dura siete segundos EN y 7,5 ES. Todos los 16 audios finales por
modelo cruzan una vez el empalme. En inglés se pasa del índice 179 al 12; en
español, del 191 al 12.

Medición fotométrica en una región facial fija, excluyendo la boca:

| Idioma | Cambio facial en empalme | Percentil 95 de vecinos normales | Relación |
| --- | ---: | ---: | ---: |
| ES | 0,02683 | 0,01919 | 1,40× |
| EN | 0,05737 | 0,02250 | 2,55× |

Valores normalizados de diferencia absoluta media RGB, no distancia anatómica
ni umbral perceptual calibrado. El caso inglés es un candidato claro a revisión
por su discontinuidad relativa. Las imágenes de inicio/fin están en los contactos.

Las comprobaciones anteriores de saltos validaban especialmente avances de
dos o más frames. El paso normal que vuelve al inicio del ciclo no exige ese
mismo control de empalme; pasar esos tests no garantiza un cierre de ciclo suave.

**Optimización propuesta:** buscar dentro del banco un par salida/entrada con
pose, mirada, párpados y velocidad compatibles; comprobar también la unión de
último a primero. Evaluar en reproducción y cuadro a cuadro, con audio y sin él.
No ocultarlo con un fundido largo ni invertir la secuencia de habla.

### 4. La voz inglesa aún supera el objetivo en frases rápidas

Consejos originales EN: mediana 3,13 palabras/s; ajustados: 2,95. Máximo del
consejo 3,63 → 3,41. Por frase, el máximo es 4,20 → 3,93 palabras/s.
ES: mediana del consejo 2,95 → 2,91; máximo 3,06 → 3,01.

El objetivo EN de 2,65 palabras/s no es una garantía: la regla limita la reducción
a un factor mínimo 0,90 y utiliza una primera medición. Tras regenerar, comprueba
que se ralentizó realmente, pero no repite hasta alcanzar la meta.

**Optimización propuesta:** medir la segunda síntesis y señalar frases que
siguen demasiado rápidas; probar una segunda corrección acotada y cacheada sólo
para esas frases EN. Evaluar el costo antes de desplegar: una doble síntesis
puede aumentar espera y CPU. Primero corregir el selector: ralentizar todo no
resuelve una boca mal etiquetada o ausente en el recorrido.

## Límites de las skills y de las métricas

- El pHash agrupó los **408 frames en un solo grupo**, incluso entre idiomas.
  No implica que sean sustituibles: la escena está casi fija y los cambios de
  boca/párpados ocupan pocos píxeles. **No usar ese resultado para borrar frames.**
  Cualquier deduplicación futura debe comparar regiones y función temporal.
- Ojos cerrados no significan un frame defectuoso: son parte del parpadeo.
- Prosody Lens se ejecutó con pausas de baja energía de al menos 250 ms. Eso no
  cubre las pausas insertadas de 160/80/20 ms de nuestro sistema. No sustituir
  sus marcas PCM por las regiones de este informe.
- El pitch fallback alcanza un borde de búsqueda en cinco de los ocho informes.
  No usar esas cifras para clasificar fonemas ni justificar cambios de voz.
- El texto está disponible, pero la posición de palabras en Prosody Lens es
  aproximada. El ritmo exacto por segmento del relevamiento procede de la
  duración de la síntesis y los metadatos de la app, no de esos marcadores.
- Los informes Prosody incluyen voz reproducible localmente. No se enviaron a
  servicios externos ni se ejecutaron APIs pagas. El análisis convierte una
  copia a 16 kHz; los WAV originales permanecen intactos. En estos ocho casos
  no se recortaron los bordes activos.
- Los porcentajes RF/TDNN siguen siendo concordancia con referencias débiles.
  No describen por sí solos naturalidad o fluidez visual.

## Orden de trabajo recomendado

1. Mantener el modelo RF como referencia experimental; conservar el español
   publicado. Revisar las etiquetas de apertura/cierre por frame, empezando por
   los casos documentados y los bordes de transiciones.
2. Corregir y probar el empalme EN; incluirlo en la verificación de continuidad.
3. Con el mismo audio y etiquetas revisadas, comparar el recorrido actual con
   secuencias cortas alternativas. No agregar imágenes salvo una carencia concreta.
4. Medir nuevamente pausas y cierres visibles sobre frases reservadas y evaluar
   una segunda corrección de voz EN sólo si sigue siendo necesaria.
5. Reentrenar cuando las referencias revisadas aporten información nueva. Añadir
   ejemplos difíciles y una evaluación independiente, sin prometer 80 %.

No se aplicó ninguna de esas modificaciones al producto en este relevamiento.
Se generaron únicamente scripts de auditoría e informes locales.

## Archivos y verificación

Abrir `tmp/isa-own-classifier/skills-audit-v1/index.html` como índice de evidencia.
En ese directorio quedan `summary.json`, `audio-audit.json`, `facial-audit.jsonl`,
`frame-index.json`, `animation-paths.json`, los contactos y ocho informes de voz.
Se probaron reproducción, seeking, controles y exportación PNG de Map/Card/Library
en un informe por idioma, sin errores de consola ni red y sin desborde móvil.

Reproducción desde el backend:

```powershell
python experiments/isa_classifier/skill_audit.py --frontend ../app-clima --corpus tmp/isa-own-classifier/corpus-tdnn-v1/corpus.json --output tmp/isa-own-classifier/skills-audit-reproduction --mode extract
python experiments/isa_classifier/skill_audit.py --frontend ../app-clima --corpus tmp/isa-own-classifier/corpus-tdnn-v1/corpus.json --output tmp/isa-own-classifier/skills-audit-reproduction --mode audio
```

`audit_skill_plans.mjs`, `summarize_skill_audit.py` y `check_skill_reports.mjs`
completan la inspección. El entorno de skills está fuera del proyecto, en
`C:/Users/rocii/.codex/skill-runtimes/isa-media`.
