# Recursos de Isa para la siguiente fase

Historial de generación: [prompts originales de imágenes y videos](PROMPTS-ORIGINALES.md).
Esta guía contiene los pedidos actuales para preparar las bocas de Rhubarb.

La fase 3 ya analiza el audio de Piper con Rhubarb. Falta preparar las formas
de boca y probar su reproducción; los atlas actuales siguen en uso.

## Paso 1: reutilizar la imagen frontal existente

**No generar otra imagen base.** Se revisaron visualmente estos recursos:

- `clima/app-clima/public/isa-bot/isa-originales-backup/original/mirando-al-frente.jfif`:
  salida original de Gemini en JPEG/JFIF, de 2240 × 1914.
  **Usar este archivo como referencia preferida en los nuevos pedidos.**
- `clima/app-clima/public/isa-bot/original/mirando-al-frente.webp`: original de
  producción convertido a WebP, también de 2240 × 1914, con ojos abiertos,
  mirada al frente y labios cerrados. Conserva la resolución, pero no es el
  archivo fuente descargado de Gemini.
- `clima/app-clima/tmp/isa-local-audit/isa-reference-front.png`: cuadro frontal
  extraído del atlas de producción, de 320 × 320, fuera de Git. Sirve para
  comparar el encuadre del renderizador; no sustituye al original de mayor
  resolución para generar variantes.

Control de fuentes realizado el 15 de noviembre de 2026: el PNG de Photoroom
del backup también conserva 2240 × 1914; el PNG extraído del atlas mide
320 × 320. PNG no reduce la resolución por sí mismo: importa cuál de estos
archivos se adjunta y si fue redimensionado. Usar el JFIF fuente evita una
conversión o extracción adicional, pero no garantiza que Gemini mantenga el
encuadre ni demuestra que la resolución fuera la causa de la primera variante
desalineada.

La imagen frontal existente será la referencia del estado X de reposo.
No volver a transformar fotos de la persona ni pedir una versión nueva de Isa.
Conservar las dimensiones, proporciones, encuadre, fondo blanco e iluminación
**del original adjunto**; no pedir un formato cuadrado ni 1024 × 1024 si eso
cambia su formato. La preparación al tamaño del renderizador se hará después,
con el mismo procedimiento para todos los estados.

## Paso 2: generar solamente las variantes de boca, por separado

### Dónde guardar los archivos

Carpeta del frontend: `clima/app-clima/public/isa-bot/rhubarb/`.

```text
rhubarb/
  original/    # Salidas originales de Gemini, sin sobrescribirlas al convertir
  con-fondo/   # Versiones WebP con el fondo original
  sin-fondo/   # Versiones WebP con transparencia real
```

Usar el mismo nombre base en las tres carpetas: por ejemplo,
`original/isa-mouth-A.jfif`, `con-fondo/isa-mouth-A.webp` y
`sin-fondo/isa-mouth-A-Photoroom.webp`. Conservar la extensión real del original si Gemini
entrega otro formato. No convertir cambiando solamente la extensión.

Los maestros JFIF y el backup son locales y están ignorados por Git. Los WebP
sí se versionan. Angular excluye estos candidatos del build mientras no estén
integrados; las carpetas locales no se borran al agregar las exclusiones.

Las dos versiones WebP deben conservar idénticas dimensiones, posición y escala
del personaje. Al quitar el fondo, no recortar ni recentrar automáticamente cada
imagen. Revisar juntas las variantes antes de integrarlas; todavía no las carga
el renderizador. Para X reutilizar el frontal existente y conservar su archivo
fuente. No hace falta generarlo de nuevo.

### Pedidos separados

Adjuntar siempre el mismo original frontal y pedir **una variante por pedido**.
No usar la variante anterior como referencia para la siguiente.

El conjunto completo tendrá **9 estados**: X reutilizado más A, B, C, D, E, F,
G y H. Por tanto, serían **8 imágenes nuevas como máximo**. Si omitimos H y
la desactivamos en Rhubarb, serán **7 imágenes nuevas** y 8 estados en total.
A es un cierre con presión para m/p/b; se revisará si el recurso existente
puede representarlo antes de generar un duplicado. No pedir todos los estados
juntos ni un video.

### Plantilla para cada pedido

Se retoma el formato breve que Nahuel usó para las poses anteriores. Adjuntar
el original frontal, sin usar la primera variante A rechazada como referencia.
Reemplazar solamente la descripción de la boca en cada pedido:

Estos pedidos se envían en el modo imagen de Gemini, uno por vez; no hace falta
repetir «una sola imagen» ni «sin video» en el texto.

> Una pose por vez, adjuntando siempre esta imagen original que me generaste:
>
> Mirando al frente, ojos abiertos, cejas relajadas y expresión amable. [FORMA DE BOCA DE LA TABLA], con las comisuras suavemente elevadas cuando la forma lo permita. Cambiá únicamente la boca de la primera imagen generada en este chat. Conservá el resto del rostro, el cuerpo, la ropa, la computadora y el fondo, con el mismo encuadre y proporciones. Dimensiones: 2240 píxeles de ancho × 1914 píxeles de alto.

### Primer pedido corregido: boca A

> Una pose por vez, adjuntando siempre esta imagen original que me generaste:
>
> Mirando al frente, ojos abiertos, cejas relajadas y expresión amable. Labios juntos con ligera presión, como al pronunciar «m», sin mostrar los dientes, sin fruncirlos hacia adelante y con las comisuras suavemente elevadas. Cambiá únicamente la boca de la primera imagen generada en este chat. Conservá el resto del rostro, el cuerpo, la ropa, la computadora y el fondo, con el mismo encuadre y proporciones. Dimensiones: 2240 píxeles de ancho × 1914 píxeles de alto.

Tras completar la generación, se organizaron las candidatas con nombres
`isa-mouth-A.jfif` a `isa-mouth-H.jfif` y se copió el reposo existente como
`isa-mouth-X.jfif`. La última A y B-v4 sustituyen los ensayos anteriores de A/B,
eliminados por pedido de Nahuel. A–H miden 2240 × 1920 y X, 2240 × 1914.
G/H quedan pendientes de validar por su forma de boca. El registro completo
está en [la selección de recursos del frontend](../../../app-clima/docs/isa-local/MOUTH-ASSETS.md).
El prompt breve es una nueva prueba, no garantiza por sí solo que el generador
mantenga los píxeles fuera de la boca.

Revisar cada resultado contra el original: un generador puede mover el rostro
aunque el prompt lo prohíba. No integrar variantes desalineadas sin corregirlas.

Pedir ediciones separadas sobre **la misma imagen aprobada**, cambiando solo la
región de labios/mandíbula necesaria. Una imagen por variante; nada de movimiento
de cabeza, parpadeo ni cambio de expresión. Primer conjunto para explorar:

- Reposo con boca cerrada, relajada: ya disponible; reutilizar X.
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
| `isa-mouth-X.png` | Reutilizar el original frontal con labios cerrados; preparar PNG al integrar |

Mantener el mismo rostro y encuadre en todos los archivos. A/X pueden parecerse,
pero son estados diferentes. B/C/E también deben distinguirse sin mover la cabeza.
H es opcional: si el estilo no permite ver la lengua, se puede desactivar esa
forma al configurar el reconocedor, sin inventar una imagen incorrecta.

No son nueve fonemas ni nueve emociones. Son formas visuales que agrupan sonidos;
la correspondencia acústica en español se revisa escuchando las muestras.
Ver [catálogo oficial](https://github.com/DanielSWolf/rhubarb-lip-sync#mouth-shapes).
Rhubarb crea los tiempos para cada audio, no estas imágenes. El ensayo agrega
las marcas al WAV pero el renderizador actual todavía no las reproduce.
