# Voz y animación con velocidad automática · 16/11/2026

Visor final: `tmp/isa-own-classifier/automatic-rate-v2/index.html`.
Izquierda: ritmo actual. Derecha: velocidad automática, con nuevas marcas y
plan de animación propios. Se escucha una variante por vez, ambas a 1× real.

## Automatización experimental

1. Sintetizar el texto con el director actual y el saludo/despedida de la app.
2. Medir palabras/s de cada fragmento usando sus tiempos reales `isac`.
3. Reducir sólo el consejo que excede el objetivo: inglés 2,65 palabras/s,
   español 2,85. Límite de reducción: 10 % inglés y 6 % español; no acelerar
   frases lentas ni modificar saludo, despedida o pausas insertadas.
4. Regenerar con factores por frase, volver a obtener alineaciones de esa misma
   síntesis, ejecutar el híbrido congelado y calcular un nuevo plan de frames.

Es una regla de dos pasadas; no un nuevo modelo entrenado, un optimizador
convergente ni un control en tiempo real dentro de cada palabra. Los objetivos
son hipótesis para escuchar, no velocidades naturales óptimas demostradas.
Dos síntesis aumentan el trabajo/latencia; no se integró al endpoint de producción.
El límite puede impedir llegar al objetivo (ocurre en la segunda frase inglesa).

## Resultado medido en la muestra

| Consejo | Factor decidido | Palabras/s antes | Después |
| --- | ---: | ---: | ---: |
| EN: It may rain this afternoon. | 0,9661 | 2,74 | 2,67 |
| EN: Bring a light jacket… | 0,90 | 3,04 | 2,81 |
| ES: Esta tarde puede llover. | 0,9844 | 2,90 | 2,85 |
| ES: Llevá una campera… | 1 | 2,85 | 2,85 |

Se reinicia la sesión ONNX y su semilla para cada variante, controlando mejor
la variación de síntesis. En esta comparación saludo y despedida mantienen sus
duraciones. La muestra inicial v1 sin esta comparación emparejada se conserva,
pero no se usa como visor final: mezclar generaciones aleatorias podía confundir
el efecto de cambiar la velocidad con variaciones naturales de Piper.

Ambas variantes usan el mismo banco visual y planificador, con aceleración local
de cierres inglesa y perfil español conservado. No se frena el audio en el
reproductor ni se estiran marcas del WAV anterior. La selección de frames se
recalcula según el reloj absoluto de cada audio. Falta evaluación humana para
decidir si la coordinación y naturalidad mejoran; no se afirma una ganancia
porcentual de precisión ni que se haya corregido el caso anterior de 3,151 s.

## Validación

59 pruebas Python. Playwright comprobó ES/EN, narración, reproducción real 1×,
exclusión entre audios, animación, búsqueda temporal, móvil sin desbordamiento y
ausencia de solicitudes externas. Se comprobó duración mayor en cada fragmento
seleccionado y conservación de pausas insertadas.

## Reproducción

```powershell
.\tmp\isa-phoneme-env\Scripts\python.exe -X utf8 experiments/isa_classifier/prepare_auto_rate_demo.py --source tmp/isa-own-classifier/hybrid-animation-v1 --output tmp/isa-own-classifier/automatic-rate-nuevo
node experiments/isa_classifier/build_auto_rate_demo.mjs ../app-clima tmp/isa-own-classifier/automatic-rate-nuevo
node experiments/isa_classifier/check_auto_rate_demo.mjs ../app-clima tmp/isa-own-classifier/automatic-rate-nuevo
```

Usar una carpeta nueva. `comparison.json` y `case-es/en.json` conservan las
decisiones, tiempos medidos y hashes PCM. Producción y corpus previos intactos.
