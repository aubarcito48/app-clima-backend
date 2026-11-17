# V7 · 128 audios y señales temporales · 16/11/2026

Se completó la ronda definida en [PROTOCOL-V7.md](PROTOCOL-V7.md), sin reajustar
los parámetros mirando la prueba final. Todo permanece fuera de producción.

## Datos

- **128 grabaciones**, 1013,59 s de narración completa (16 min 54 s), incluidos
  565,99 s de consejo hablado. 32 reutilizadas sólo de entrenamiento V6 y 96 nuevas.
- Por idioma: 40 entrenamiento, 8 desarrollo y **16 prueba**. La prueba final
  creció de 8 a 32 grabaciones en total; los nuevos consejos siguen siendo breves.
- Saludo, consejo, despedida y pausas de la app en todos los audios. Se mide
  principalmente el consejo, excluyendo las frases repetidas de entrada y cierre.
- Se verificaron frases/PCM de prueba contra V3/V4/V5/V6 y duplicados internos.
- Etiquetas de Rhubarb **sin revisión humana**, no verdad fonética validada.
- Se generó secuencialmente con Piper y Rhubarb locales, sin APIs externas.

## Clasificación del consejo en las mismas 32 grabaciones nuevas

| Modelo | Español: concordancia | Español: F1 macro | Inglés: concordancia | Inglés: F1 macro |
| --- | ---: | ---: | ---: | ---: |
| V6 congelado | 53,7 % | 29,2 % | 57,5 % | 46,8 % |
| Más audios, señales originales | 58,6 % | 32,0 % | **59,7 %** | **49,6 %** |
| **Ganador V7 de desarrollo** | **60,1 %** | **34,8 %** | **59,7 %** | **49,6 %** |

Concordancia: media por grabación; F1 macro: por forma de boca, agrupando ventanas
del consejo. No son porcentajes de calidad visual. En este conjunto V7 mejora
concordancia en 16/16 grabaciones españolas y 12/16 inglesas frente a V6.
La diferencia media de concordancia es +6,36 puntos/es y +2,17 puntos/en.

Las cifras V6 de informes anteriores se calcularon en otras frases. La tabla
evalúa el mismo V6 congelado y ambos candidatos nuevos sobre exactamente los
mismos consejos y audios finales. No se alcanzó 80 % y no se acredita todavía
una sustitución segura de Rhubarb por estos porcentajes.

## Qué aportó la información nueva

`rhythm_features.py` añade diez señales de energía relativa, baja energía,
duración transcurrida/restante de tramos de actividad, cambios de energía,
cambio espectral y densidad de inicios de actividad. Sólo recibe PCM; no ve las
etiquetas, texto ni salida Rhubarb al inferir. Usa el WAV completo, no streaming.

Se compararon 48 configuraciones prefijadas por idioma con selección por F1
macro de desarrollo y concordancia como desempate. La ampliación temporal ganó
en español. En inglés ganó el perfil original con más audios, por lo que no
se forzó la incorporación de canales que no ganaron en desarrollo.

- Español: perfil `acoustic-timing-v1`, no lineal escala 0,5, balance 0,5,
  regularización 100 y transiciones 0,05; JSON de 834 045 bytes.
- Inglés: perfil `acoustic-v1`, no lineal escala 1,5, balance 0,5,
  regularización 100 y transiciones 0,05; JSON de 608 855 bytes.
- V6 y todas las rondas anteriores se conservan. La inferencia elige explícitamente
  26 o 36 señales según el modelo; se rechazan perfiles desconocidos o faltantes.
- No se midió consumo máximo ni latencia del endpoint en Render. El modelo
  español creció considerablemente respecto al lineal V6; debe medirse antes de integrar.

## Pausas y cierres: resultados separados

Se calculó una métrica independiente para las pausas realmente insertadas por
Piper: fracción de ventanas con salida A/X (labios cerrados/reposo). No es la
precisión global ni se usa para afirmar que el clasificador llegó a 80 %:

| Boca cerrada durante pausa conocida | V6 | V7 |
| --- | ---: | ---: |
| Español | 87,5 % | 83,5 % |
| Inglés | 99,6 % | 99,6 % |

La caída española muestra un pendiente concreto aunque mejoren las métricas del
consejo. También se midieron cierres cuando la referencia acústica pide apertura:
español bajó de 6,0 % a 4,9 %; inglés subió ligeramente de 7,4 % a 7,6 %.
No todo mejoró y las fronteras/etiquetas todavía necesitan revisión humana.

## Animación: auditoría aparte

Se verificaron **128 planes visuales**: 32 audios × V6/V7 × con/sin aceleración
local. Se comprobaron avance monótono, límites de desplazamiento, pose y movimiento.
El banco no cambió ni se añadieron imágenes; los 24 candidatos siguen separados.

En las 16 grabaciones inglesas, la aceleración redujo la discrepancia visual
heurística de cierres prolongados con V7: suma de 6000 ms antes a 2125 ms después.
No aumentó ese indicador en ninguna de esas 16. Con V6, pasó de 5917 a 2167 ms.
Esto confirma el ajuste visual en más ejemplos, **no mejora la precisión acústica**.
Los datos se basan en etiquetas visuales provisionales y actividad energética.
La aceleración española sigue desactivada por defecto; sus resultados no cambian
al comparar con/sin esa función.

## Pruebas para escuchar

- `tmp/isa-own-classifier/animation-v7/index.html`: V7/V6 frente a Rhubarb con el
  selector actual. Conserva el mismo PCM del ensayo V6 para aislar el nuevo modelo.
- `tmp/isa-own-classifier/timing-v3/index.html`: laboratorio actual con V7 y el
  ajuste local de ritmo. El nombre `timing-v3` es la versión del laboratorio,
  no la versión del clasificador.

Ambos mantienen saludo, consejo y despedida. El selector español actual puede
dar planes idénticos aunque cambien las marcas; la demo lo avisa y no cuenta
esa coincidencia como un acierto del clasificador.

Pasaron 48 pruebas Python, el chequeo de las 32 líneas de tiempo contra el
validador actual, la auditoría de planes y los chequeos de navegador de ambas
demos: audio, perfiles, apertura/cierre, búsqueda, tema/ancho móvil cuando aplica,
sin solicitudes HTTP externas. Se inspeccionó una captura del laboratorio V7.
No hubo commit, push ni despliegue de esta etapa.

## Reproducir

Desde la raíz del backend, con las dependencias/modelos/cachés locales anteriores:

```powershell
python experiments/isa_classifier/build_expanded_plan.py --output tmp/isa-own-classifier/corpus-v7/additions.json
python experiments/isa_classifier/prepare_next_corpus.py --previous tmp/isa-own-classifier/corpus-v6/corpus.json --additions tmp/isa-own-classifier/corpus-v7/additions.json --output tmp/isa-own-classifier/corpus-v7
.venv/Scripts/python.exe experiments/isa_classifier/generate_corpus.py --plan tmp/isa-own-classifier/corpus-v7/plan.json --output tmp/isa-own-classifier/corpus-v7
python experiments/isa_classifier/train_rhythm.py --corpus tmp/isa-own-classifier/corpus-v7/corpus.json --previous-corpus tmp/isa-own-classifier/corpus-v3/corpus.json --previous-corpus tmp/isa-own-classifier/corpus-v4/corpus.json --previous-corpus tmp/isa-own-classifier/corpus-v5/corpus.json --previous-corpus tmp/isa-own-classifier/corpus-v6/corpus.json --reference-v6 tmp/isa-own-classifier/v6 --output tmp/isa-own-classifier/v7
node experiments/isa_classifier/check_visual_batch.mjs ../app-clima tmp/isa-own-classifier/v7
python -m unittest discover -s experiments/isa_classifier -p test_*.py -q
```

Las salidas detalladas están en `v7/evaluation.json` y `v7/visual-evaluation.json`,
bajo `tmp/` ignorado. La próxima ronda debe reservar otras frases: estas 32 ya
fueron observadas y no deben usarse para elegir nuevos parámetros.
