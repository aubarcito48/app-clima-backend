# Aceleración local de cierres visuales · 16/11/2026

Abrir `tmp/isa-own-classifier/timing-v2/index.html`. La prueba V1 se conserva.

Se atendió el tramo inglés señalado por el usuario en torno a **5,55 s**. No
había una pausa larga insertada del audio: el banco recorría once frames
consecutivos etiquetados como cerrados, de 5,292 a 5,750 s (~458 ms). Dentro
de ese tramo V6 sólo proponía un cierre breve de ~70 ms. Las etiquetas son
provisionales, pero la captura del usuario también mostraba el cierre prolongado.

La corrección **no elimina imágenes del banco**. Recorre más rápido un tramo
de boca cerrada mientras hay evidencia de voz y el objetivo pide reapertura.
Puede prepararse durante los últimos ~83 ms de un cierre breve, manteniendo
la boca cerrada mientras corresponde. Se limita a transiciones ya medidas
como compatibles por pose/movimiento, sin mezclar tomas ni acelerar la voz.

En el caso reproducido, el cierre del nuevo plan dura **167 ms**, de 5,458 a
5,625 s. Sigue siendo más largo que la marca acústica débil de ~70 ms; no se
declara sincronización perfecta ni se fuerza un salto que exceda los límites
de continuidad. La comparación utiliza exactamente el mismo WAV.

## Detección y reproducción

- El detector busca secuencias de frames cerrados que se extienden sobre voz
  activa mientras las marcas piden otra forma. La tabla ofrece reproducir cada
  tramo y comparar duración antes/después.
- La evidencia de voz usa energía local y contexto de ±25 ms. No puede probar
  qué palabra o fonema se pronuncia; las alertas siguen sin revisión humana.
- Se excluyen pausas insertadas conocidas y candidatos largos de baja energía.
  Se conserva la protección de cierres breves de las marcas acústicas.
- La opción «Acelerar cierres visuales largos durante la voz» está activa
  inicialmente para inglés y desactivada para español. Cada voz conserva su perfil.
- El avance extraordinario sólo atraviesa frames intermedios cerrados, con
  desplazamiento acotado y guardas de pose ≤0,04 y movimiento ≤0,025.
- La reproducción utiliza interpolación Hermite monótona para suavizar cambios
  de velocidad sin rebobinar ni acumular desfase. El reloj sigue siendo el audio.
- Durante una aceleración, el refresco de pantalla puede no dibujar todos los
  frames intermedios; eso no elimina archivos ni cambia el banco original.

## Verificación

El caso de 5,55 s tiene regresión automática: compara antes/después, exige
reducción del cierre y de su exceso durante voz activa, valida todas las guardas
de transición y comprueba monotonicidad a 240 muestras/s y búsqueda sin desfase
acumulado. Pasaron 43 pruebas Python, las verificaciones del planificador y
el chequeo de navegador con activación/desactivación, perfiles independientes,
audio, búsqueda, exportación y ancho móvil. No hubo cambios de producción.

```powershell
node experiments/isa_classifier/build_timing_lab.mjs ../app-clima tmp/isa-own-classifier/timing-v2
node experiments/isa_classifier/check_closure_fix.mjs ../app-clima tmp/isa-own-classifier/timing-v2
node experiments/isa_classifier/check_timing_lab.mjs ../app-clima tmp/isa-own-classifier/timing-v2
node experiments/isa_classifier/test_timing_planner.mjs
python -m unittest discover -s experiments/isa_classifier -p test_*.py -q
```

V2 reutiliza `timing.json` de V1: mismo audio con saludo/consejo/despedida,
sin generación de voz nueva, llamadas de API ni otra ronda de entrenamiento.
