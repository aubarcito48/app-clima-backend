# Laboratorio de boca, ritmo y pausas · 16/11/2026

Abrir `tmp/isa-own-classifier/timing-v1/index.html` en un navegador.
Es un HTML autónomo: audio, modelos de selección y atlas están embebidos.
No requiere servidor ni usa APIs. Conserva saludo, consejo y despedida exactos
de la app en español e inglés, reutilizando los PCM de la demo V6.

## Qué compara

Izquierda: selector actual, con V6 por defecto o Rhubarb como control opcional.
Derecha: V6 con un selector experimental de frames completos y tiempos ajustables.
La comparación inicial usa las mismas marcas V6 a ambos lados para aislar el
efecto del selector. Si se elige Rhubarb a la izquierda, cambian dos componentes;
no atribuir entonces toda diferencia sólo al ajuste temporal.

No hay reentrenamiento ni nueva cifra de precisión en esta etapa. La prioridad
es poder medir y revisar coordinación, sin cambiar ojos/expresiones ni producción.

## Tiempos realmente disponibles

`analyze_timing.py` lee el PCM y los tiempos `isac` reales de Piper, y verifica
texto/fragmentos con el plan de actuación. Se muestran:

- Inicio y fin hablado de saludo, fragmentos del consejo y despedida.
- Pausas **insertadas conocidas** entre fragmentos y duración exacta.
- Intervalos de baja energía con ventanas de ~5 ms, clasificados por duración
  como candidatos cortos/largos. No se presentan como silencios confirmados.
- Palabras por segundo medias de cada fragmento y del consejo completo.

En estas muestras, el consejo español dio 2,92 palabras/s y el inglés 2,93.
Se detectaron 10/18 intervalos candidatos de baja energía y dos pausas insertadas
en cada audio. Eso no prueba que Cori sea siempre más rápida, ni que cada intervalo
sea un límite entre palabras; ritmo local, articulación y longitud de palabras
también afectan la percepción. Se conservan perfiles independientes por voz.

**No hay alineación automática por palabra.** Una consonante poco sonora puede
parecer silencio y un espacio escrito puede no tener pausa audible. Las frases
se identifican sólo cuando existe un final de fragmento conocido con puntuación;
el detector de energía no inventa palabras ni oraciones.

## Controles y selector experimental

- Desfase general: ±250 ms. Positivo anticipa el objetivo respecto del audio.
- Apertura y cierre: ±150 ms, independientes; se aplican a intervalos cerrados
  sin borrar los cierres breves si las compensaciones entran en conflicto.
- Tiempo mínimo entre ajustes de avance: 40–350 ms. Controla cuán seguido puede
  retener o saltar un frame, no la duración de cada fonema ni la velocidad de voz.
- Pausas acústicas candidatas: desactivadas inicialmente. Activarlas es una
  hipótesis para escuchar, con duración mínima ajustable; no valida sus etiquetas.
- Perfiles separados ES/EN y descarga JSON con `experimental: true, reviewed: false`.
  Las opciones inválidas no reemplazan un perfil válido ni su plan.

El selector usa programación dinámica sobre toda la muestra, pasos 0/1/2 y un
desplazamiento limitado respecto de la secuencia nativa. Los saltos sólo se
permiten con los límites de pose/movimiento ya medidos en el catálogo. No se
mezclan tomas, pegan partes de cara ni añaden imágenes. Los frames vienen del
mismo banco y mantienen ojos, rostro y cuerpo completos.

El tiempo de salida se consulta como función absoluta del instante del audio;
buscar hacia atrás/adelante o aplicar un perfil no acumula retraso ni reinicia
la voz. Mantener sincronía del reloj no garantiza acertar la forma o el instante
perceptual: eso todavía requiere revisión.

El selector español aprobado queda a la izquierda, incluidos sus ciclos nativos
completos. El ensayo derecho sí puede ajustar su avance dentro de esos ciclos;
no se cambia el comportamiento publicado para lograr la comparación.

## Parámetros iniciales y límites observados

Los valores son hipótesis iniciales, no calibración aprendida ni aprobada:

| Parámetro | Español | Inglés |
| --- | ---: | ---: |
| Desfase general / apertura / cierre | 0 / 0 / 0 ms | 0 / 0 / 0 ms |
| Tiempo entre ajustes | 125 ms | 83 ms |
| Desplazamiento máximo | 4 frames | 6 frames |
| Candidato acústico mínimo, si se activa | 90 ms | 70 ms |

Con los valores iniciales, la muestra española produjo 4 retenciones y 3 saltos;
la inglesa, 8 y 9. Las etiquetas provisionales pidieron 25/48 instantes de boca
cerrada, de los que 12/30 no obtuvieron un frame etiquetado como cerrado bajo las
restricciones. Esto es un diagnóstico del banco/selector, **no precisión** ni
prueba de que esas etiquetas sean correctas.

Es un indicio para revisar unos pocos cierres y transiciones compatibles antes
de ampliar el banco. El desplazamiento de fase alcanzó 41,7 ms/es y 166,7 ms/en
respecto de la secuencia nativa; no equivale al desfase audiovisual real.
Con 24 fps, un frame dura ~41,7 ms: controles más finos no crean nuevos frames.

## Verificación y trabajo pendiente

Pasaron 43 pruebas Python, verificaciones Node del planificador y un chequeo de
navegador en ambos idiomas: reproducción, pausas candidatas opcionales, cambios
independientes, exportación, rechazo de perfiles inválidos, persistencia ES/EN
en la sesión, búsqueda, ancho móvil y cero solicitudes HTTP externas.
Se inspeccionó una captura completa del laboratorio inglés.

Próximo paso: escuchar ejemplos de cierres, marcar fronteras reales de palabra
y movimientos y guardar ajustes revisados por voz. Los perfiles descargados
todavía no están validados ni se cargan en producción. No se hizo commit/push.

## Reproducir desde el backend

```powershell
python experiments/isa_classifier/analyze_timing.py --demo tmp/isa-own-classifier/animation-v6 --output tmp/isa-own-classifier/timing-v1
node experiments/isa_classifier/report_timing.mjs ../app-clima tmp/isa-own-classifier/timing-v1
node experiments/isa_classifier/build_timing_lab.mjs ../app-clima tmp/isa-own-classifier/timing-v1
python -m unittest discover -s experiments/isa_classifier -p test_*.py -q
node experiments/isa_classifier/test_timing_planner.mjs
node experiments/isa_classifier/check_timing_lab.mjs ../app-clima tmp/isa-own-classifier/timing-v1
```
