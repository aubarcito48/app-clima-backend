# Isa: prompts originales de imágenes y videos en Gemini

Registro de los prompts compartidos por Nahuel el 15 de noviembre de 2026,
usados anteriormente para crear los recursos de Isa. Se conserva su redacción
como referencia histórica. No implica que podamos reconstruir una salida
idéntica: no se registraron aquí la versión del generador, la semilla ni las
imágenes adjuntas originales de cada ejecución.

## Imagen inicial: creación del personaje

Se adjuntaban fotos de la persona como referencia, incluyendo una vista de lado.

> Transforma a la persona de la primera foto en un personaje 3D al estilo Pixar. Te deje dos fotos mira que tengas referencia mirando de lado. Mantén su rostro, cabello, tono de piel y sonrisa reconocibles. Está sentada frente a una computadora portátil sobre un escritorio blanco liso, de frente, mirando a la cámara. Iluminación suave de estudio, fondo blanco limpio, sin texto.

## Imagen de reposo: una pose por vez

Instrucción compartida junto con el pedido:

> una pose por vez, adjuntando siempre esta imagen original que me generaste:
>
> 1. Reposo: mirando al frente, ojos abiertos y boca cerrada.

El recurso existente revisado para reutilizar en la fase 3 es
`clima/app-clima/public/isa-bot/original/mirando-al-frente.webp`, relativo a la
raíz del espacio de trabajo. No hace falta volver a generar esa pose.

## Video de miradas: 8 segundos

Adjuntar la imagen del personaje ya generado.

> Animá exactamente al personaje de la imagen, conservando su identidad, edad, rostro, cabello rizado con canas, ropa y computadora. Cámara completamente fija, sin zoom, desplazamientos ni cortes. Durante 8 segundos: empieza mirando a la cámara con una sonrisa suave y la boca cerrada; gira lentamente la cabeza hacia la derecha de la imagen, después hacia la izquierda; regresa al centro, mira ligeramente hacia arriba y luego hacia abajo; termina mirando nuevamente a la cámara, en la misma postura inicial. Movimientos suaves y moderados, con pausas breves en cada dirección y parpadeos naturales. El torso, las manos, la computadora y la mesa permanecen inmóviles. El fondo blanco y la iluminación permanecen constantes. Sin hablar, sin gesticular con las manos, sin agregar elementos.

## Video de habla: 8 segundos

Adjuntar la imagen del personaje ya generado. Este pedido produce movimiento
de habla genérico; no establece correspondencia con un audio de Piper concreto.

> Animá exactamente al personaje de la imagen, conservando su identidad, edad, rostro, cabello rizado con canas, ropa y computadora. Cámara completamente fija, sin zoom, desplazamientos ni cortes. Durante 8 segundos: empieza mirando a la cámara con una sonrisa suave y la boca cerrada; después mueve los labios y la mandíbula como si estuviera explicando un consejo del clima con calidez y energía moderada. Alterna aperturas pequeñas y medianas de la boca, cierres completos y pausas breves, con movimientos naturales y suaves, sin exageraciones. Mantiene la mirada al frente y la cabeza prácticamente inmóvil, con parpadeos naturales. Durante el último segundo, cierra suavemente la boca y termina mirando nuevamente a la cámara, con la misma expresión y postura iniciales. El torso, las manos, la computadora y la mesa permanecen inmóviles. El fondo blanco y la iluminación permanecen constantes. Sin girar la cabeza, sin gesticular con las manos, sin agregar elementos, texto ni subtítulos. Video silencioso y cuadros nítidos, sin desenfoque de movimiento fuerte.

## Uso futuro y diferencia con Rhubarb

- Conservar estos prompts como historial; registrar cualquier adaptación por separado.
- Mantener identidad, ropa, iluminación, fondo y cámara consistentes entre recursos.
- Los requisitos del prompt no garantizan alineación: revisar las salidas antes de integrarlas.
- Para la prueba actual de Rhubarb se reutiliza la imagen frontal existente y se
  editan formas de boca por separado. No se pide otro video de habla genérica.
- Rhubarb obtiene los tiempos desde el audio; no genera imágenes ni videos.
- Los pedidos actuales y el catálogo de bocas están en [GEMINI.md](GEMINI.md).

En futuras generaciones, guardar también el archivo de referencia adjunto,
el prompt exacto, la fecha, la herramienta/modelo y el archivo resultante.
