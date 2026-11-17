# Red temporal pequeña y referencias de pausas

Se completó el protocolo [PROTOCOL-NEURAL-TEMPORAL.md](PROTOCOL-NEURAL-TEMPORAL.md).
La red no supera a los árboles en estas frases nuevas. No se modifica producción
ni se reemplazan modelos anteriores. No se alcanza 70/80 % de concordancia.

## Referencias corregidas y límites de la corrección

Se vuelve a partir de las etiquetas originales, preservadas en los WAV. Se enlazan
con el PCM de la misma síntesis, las marcas de Piper y los huecos insertados. Sólo
una ventana de análisis de 40 ms enteramente dentro de un hueco comprobado y con
PCM exactamente cero recibe una corrección X. En train se corrigen 360 ventanas
ES y 210 EN; son las mismas correcciones fiables de la ronda anterior.

La novedad es apartar del gradiente las ventanas mixtas que intersectan un hueco
pero no quedan completamente dentro: **1.145 ES y 1.159 EN**. No se les inventa
un visema. Se entrenan dos brazos: con todas las referencias reparadas anteriores
y con esta cuarentena adicional. `reference-corrections.json` registra cada cambio,
exclusión e identidad PCM. Los originales quedan intactos.

Esto no equivale a una revisión humana completa de fonemas ni de imágenes.
Las pausas naturales, las consonantes débiles y las etiquetas visuales siguen
siendo provisionales. No se corrigen según la predicción del propio modelo.
La evaluación conserva la misma referencia para todos los modelos y brazos;
las exclusiones de frontera afectan exclusivamente al entrenamiento.

## Datos y red

Se mantienen 139 grabaciones train y 32 dev. Se generan **16 consejos finales
nuevos**, ocho por idioma, con dos velocidades verificadas: 32 audios finales.
Los tests anteriores quedan históricos; no entran en train ni en selección.
El corpus acumulado contiene 386 audios, 264 grupos, unos 56 minutos; esto no
significa que los 386 audios se usen para entrenar. Se verifican 122 pares de
velocidad del corpus y separación por grupo entre conjuntos.

Se usa una red de retardos temporales: contexto [-12,-8,-4,0,4,8,12] sobre ventanas
de aproximadamente 10 ms, capas ReLU 64/32 y salida softmax. Ve unos 240 ms de
contexto entre extremos, además del ancho de las ventanas. Es una MLP con entradas
temporales, no una RNN ni un generador de imágenes. Se entrena con Adam durante
32 épocas; checkpoints 8/16/24/32 y decodificadores se seleccionan sólo en dev.
Se comparte el balance por clase de los árboles y se reduce el peso de saludos y
de variantes duplicadas. Vocabulario y normalización proceden sólo de train.

La exportación JSON/NumPy evita pickle y coincide con las probabilidades nativas
con tolerancia 1e-12. Los archivos seleccionados pesan 977.272 bytes ES y
1.038.908 EN, bastante menos que RF. No se midió aún latencia de despliegue.
`scikit-learn==1.9.1` se mantiene en el entorno experimental. La inferencia portable
usa NumPy; no se añade un framework neuronal al backend publicado.

## Resultado final sobre los mismos consejos nuevos

Concordancia con Rhubarb y pausas comprobadas, agrupada por consejo; se excluyen
saludo, despedida y silencios insertados. **No es calidad visual humana.**

| Idioma/modelo | Concordancia | F1 macro |
| --- | ---: | ---: |
| ES XGBoost congelado | 60,81 % | 36,76 % |
| ES Random Forest congelado | 61,91 % | 34,76 % |
| ES red con referencias reparadas | 58,53 % | 33,70 % |
| ES red con fronteras apartadas, seleccionada | 57,55 % | 31,98 % |
| EN XGBoost congelado | 61,73 % | 47,50 % |
| EN Random Forest congelado | 64,27 % | 48,73 % |
| EN red con referencias reparadas | 60,19 % | 46,93 % |
| EN red con fronteras apartadas, seleccionada | 60,77 % | 47,36 % |

Las cifras de los árboles difieren de la ronda anterior porque los consejos
finales son otros. En ES RF gana concordancia, pero XGBoost gana F1 macro: no hay
un único ganador para todas las métricas. Ocho grupos por idioma son una muestra
pequeña y no permiten afirmar superioridad general.

Ambos idiomas seleccionan el brazo con fronteras apartadas, época 8, penalización
de cierre 0,25 y transición 0,05. ES lo selecciona porque pasa los controles de
cierre, aunque tenga menos F1 que el otro brazo que no los pasa. EN no encuentra
ningún candidato que pase todos los controles: se guarda sólo como diagnóstico.
Su falso cierre dev es 5,84 %, frente al máximo permitido de aproximadamente
4,54 % en este protocolo. No se reajusta usando test.

Las pérdidas train bajan hasta ~0,16, pero los checkpoints posteriores no mejoran
la selección dev. Esto es compatible con sobreajuste de esta configuración;
no demuestra que cualquier red temporal vaya a fallar ni que más épocas ayuden.

En pausas del consejo incluyendo bordes, la red mejora el cierre predicho:
ES 73,57 % RF → 89,64 % red; EN 97,31 % → 98,46 %. En interiores seguros ambos
ya alcanzan 100 % en estas muestras. Eso no se traduce automáticamente al frame.

## Continuidad visual y prueba conjunta

Se auditan 128 planes: 32 audios, RF/red y con/sin aceleración local. Todos cumplen
los límites existentes de avance monotónico, deriva, pose y movimiento de saltos
de frames. El máximo tramo adicional repitiendo un frame es ~41,7 ms. Son límites
automáticos, no una garantía de que toda transición parezca natural; los empalmes
del ciclo original y las etiquetas visuales todavía necesitan revisión perceptual.

En EN, la aceleración reduce cierres visuales incompatibles con habla activa en
16/16 audios por modelo, sin incrementarlos en ninguno. Tras aceleración el
indicador acumula 2.667 ms en la red y 2.583 ms en RF. No hay mejora frente a RF.
En ES la aceleración sigue desactivada por defecto: 12.542 ms red y 13.125 ms RF.
Son indicadores heurísticos con etiquetas provisionales, no errores humanos anotados.

Durante pausas verificadas, los frames seleccionados cierran en 63/131 instantes
ES con la red (RF 67/131) y 83/127 EN (RF 82/127). Sigue existiendo una diferencia
entre reconocer pausa y disponer/elegir una secuencia visual apropiada.

- `tmp/isa-own-classifier/neural-direct-v1/index.html`: izquierda RF, derecha red;
  mismo audio, un reloj, barras alineadas, voz con velocidad automática y
  aceleración local independiente por idioma. Incluye consejos finales nuevos.
- `tmp/isa-own-classifier/neural-review-v1/index.html`: comparación de velocidades,
  elección de clasificador y decisiones automáticas por frase.

Pasan los verificadores de reproducción simultánea, seeking, barras, retratos,
idiomas, muestras nuevas, móvil y ejecución sin red. Se inspeccionan capturas.
Pasan los 84 tests unitarios en el entorno experimental. Cubren exportación nativa/portable, aislamiento de contexto,
ventanas mixtas y conservación de referencias de evaluación. Los audios incluyen
saludos y despedidas exactos de la app. No se cambian imágenes de producción.

## Artefactos y reproducción

Bajo `tmp/isa-own-classifier/`: `corpus-tdnn-v1/corpus.json`,
`neural-temporal-v1/evaluation.json`, `reference-corrections.json` y
`pause-roles.json` dentro del directorio del modelo, y
`neural-visual-v1/visual-evaluation.json`. El reporte guarda todos los candidatos y
ambos brazos; las claves heredadas `boosted`/`identity` significan red/RF,
explicitadas por `model_names`. Los tiempos de evaluación incluyen métricas.

Entrenamiento desde la raíz del backend:

```powershell
.\tmp\isa-phoneme-env\Scripts\python.exe experiments/isa_classifier/train_neural_temporal.py --corpus tmp/isa-own-classifier/corpus-tdnn-v1/corpus.json --reference tmp/isa-own-classifier/boosted-pause-repair-v1 --forest tmp/isa-own-classifier/forest-v1 --output tmp/isa-own-classifier/neural-temporal-reproduction
```

La evidencia de esta ronda favorece conservar los árboles. El próximo trabajo útil
es revisar fonemas/fronteras y etiquetas visuales contra ejemplos concretos, y
comprobar el empalme de secuencias. No hay base para prometer 80 % con más épocas.
