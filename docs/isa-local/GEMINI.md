# Recursos de Isa para la siguiente fase

Para la fase 2 no hace falta generar imágenes. Preparar recursos ahora es opcional
y no sustituye los atlas actuales. Primero buscamos una referencia consistente;
después probaremos las formas de boca y su correspondencia con el audio.

Se extrajo el cuadro frontal real del atlas de producción, sin regenerarlo:
`clima/app-clima/tmp/isa-local-audit/isa-reference-front.png`, relativo a la raíz
del espacio de trabajo. Es una referencia local de 320 × 320, fuera de Git.
Adjuntar ese archivo a Gemini. No usar una hoja de contacto como referencia de
un personaje nuevo. Para más resolución conviene conservar además el original
del personaje; ampliar el cuadro no recupera detalle.

## Primer pedido: una sola imagen de referencia

> Usá la imagen adjunta como referencia estricta de Isa. Conservá su identidad,
> edad aparente, rostro, pelo rizado con canas, ropa roja, computadora, manos,
> pose, encuadre, perspectiva, iluminación y proporciones. Necesito una imagen
> frontal de referencia para animación de labios: boca relajada y cerrada, ojos
> abiertos y mirada al frente. No agregues accesorios, texto ni gestos. No cambies
> la posición ni el tamaño del rostro. Entregá una sola imagen PNG cuadrada,
> preferentemente 1024 × 1024, con fondo transparente si la herramienta permite
> transparencia real. Si no la permite, usá un fondo liso uniforme. No dibujes un
> damero para simular transparencia. Todavía no generes video ni una hoja de poses.

Revisar esa imagen antes de pedir variantes: si cambia el personaje o el encuadre,
las variantes heredarán el problema. No podemos garantizar alineación exacta con
un generador: se verifica y corrige antes de integrar.

## Después de aprobar la referencia

Pedir ediciones separadas sobre **la misma imagen aprobada**, cambiando solo la
región de labios/mandíbula necesaria. Una imagen por variante; nada de movimiento
de cabeza, parpadeo ni cambio de expresión. Primer conjunto para explorar:

- Reposo con boca cerrada, relajada.
- Labios juntos para sonidos como m/p/b.
- Boca ligeramente abierta, dientes cercanos.
- Apertura amplia para una vocal abierta.
- Boca estirada horizontalmente.
- Boca redondeada pequeña y boca redondeada más abierta, en archivos separados.
- Dientes superiores apoyados suavemente en el labio inferior, para f/v.

Estas descripciones son un inventario inicial, no una equivalencia definitiva de
fonemas ni las cinco vocales como única clasificación. La correspondencia final
se decidirá al evaluar las señales de audio y el reconocedor elegido. Conservá
archivos separados, resolución idéntica y nombres descriptivos; no pedir FPS ni
un video largo para este paso. Revisaremos alineación, identidad, cobertura y
transiciones antes de crear un atlas o recortar bocas.

## Correspondencia para el ensayo con Rhubarb

El ensayo de fase 3 usa Rhubarb 1.14.0 con `phonetic` y las formas extendidas
G/H/X. Su catálogo tiene seis formas básicas A–F y tres opcionales G/H/X:

| Archivo propuesto | Forma a pedir |
| --- | --- |
| `isa-mouth-A.png` | Labios juntos con ligera presión, para m/p/b |
| `isa-mouth-B.png` | Boca apenas abierta, dientes cercanos |
| `isa-mouth-C.png` | Apertura media |
| `isa-mouth-D.png` | Apertura amplia |
| `isa-mouth-E.png` | Boca un poco redondeada |
| `isa-mouth-F.png` | Labios fruncidos, redondeados |
| `isa-mouth-G.png` | Dientes superiores sobre labio inferior |
| `isa-mouth-H.png` | Lengua elevada detrás de dientes superiores |
| `isa-mouth-X.png` | Reposo relajado con labios cerrados |

Mantener el mismo rostro y encuadre en todos los archivos. A/X pueden parecerse,
pero son estados diferentes. B/C/E también deben distinguirse sin mover la cabeza.
H es opcional: si el estilo no permite ver la lengua, se puede desactivar esa
forma al configurar el reconocedor, sin inventar una imagen incorrecta.

No son nueve fonemas ni nueve emociones. Son formas visuales que agrupan sonidos;
la correspondencia acústica en español se revisa escuchando las muestras.
Ver [catálogo oficial](https://github.com/DanielSWolf/rhubarb-lip-sync#mouth-shapes).
Rhubarb crea los tiempos para cada audio, no estas imágenes. El ensayo agrega
las marcas al WAV pero el renderizador actual todavía no las reproduce.
