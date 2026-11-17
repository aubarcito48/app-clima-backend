# Entrenamiento V5 · 16/11/2026

Se amplió el corpus a **40 grabaciones, 227,14 segundos**. Se reutilizaron sólo
los veinte audios de entrenamiento de V4 y se generaron veinte nuevos: ocho
de entrenamiento, seis de desarrollo y seis de prueba. Por idioma: 14/3/3.

Los nuevos textos de entrenamiento agregan vocales redondeadas, lengua, cierres,
pausas explícitas y números. Los nuevos textos finales duran aproximadamente
7–9 segundos e incluyen recomendaciones más largas, preguntas y cambios de frase.
No se añadieron imágenes al banco ni se modificaron los 24 candidatos seleccionados.

## Protocolo

`corpus_v5_additions.json` fija los textos nuevos. `prepare_next_corpus.py`
reutiliza exclusivamente la partición de entrenamiento anterior, comprueba hashes
de PCM y rechaza cambios en destinos existentes. `train_next.py` comprueba que
las nuevas frases y PCM de desarrollo/prueba no hayan aparecido en V3 ni V4.

Se compararon 24 configuraciones prefijadas por idioma, elegidas únicamente por
F1 macro en desarrollo, con concordancia como desempate. Se evaluaron después
el ganador, el mejor lineal seleccionado en desarrollo y V3 congelado, sobre las
mismas tres grabaciones finales por idioma. No se reajustó mirando ese resultado.

**Las etiquetas siguen siendo Rhubarb sin revisión humana.** Las cifras son
concordancia con esa referencia, no calidad de animación validada. El conjunto
final ya fue observado y no debe usarse para elegir futuras configuraciones.

## Resultados sobre las mismas grabaciones nuevas

| Modelo | Español: concordancia | Español: F1 macro | Inglés: concordancia | Inglés: F1 macro |
| --- | ---: | ---: | ---: | ---: |
| V3 congelado | 49,2 % | **32,2 %** | 58,9 % | 37,3 % |
| Mejor lineal del corpus ampliado | **54,5 %** | 31,5 % | 56,0 % | 36,9 % |
| Candidato V5 elegido en desarrollo | **54,5 %** | 31,5 % | **60,3 %** | **37,5 %** |

Concordancia: media por grabación. F1 macro: por clase, combinando las ventanas
de prueba. No se comparan directamente estos porcentajes con los informes V3/V4,
que usaron otras frases. La comparación válida aquí es entre filas de esta tabla.

El avance inglés en F1 es pequeño: **0,23 puntos porcentuales**, con sólo tres
grabaciones finales. No demuestra una mejora general. En español sube la
concordancia pero cae F1 en ~0,74 puntos; por eso se conserva V3 como referencia
y no se declara que V5 sea mejor para todas las formas o idiomas.

## Variante no lineal

`temporal.py` mantiene compatibilidad con los modelos lineales anteriores y añade
una transformación de 128 características cosenoidales con proyección aleatoria
fija, concatenadas con el contexto lineal. Se normalizan con estadísticas del
entrenamiento y se ajusta la salida mediante regresión regularizada y balanceada.
La proyección aleatoria no se aprende; los coeficientes de salida sí.

- Semilla fija: 20261116. Contexto y transiciones no cruzan archivos.
- Configuraciones: lineal o escalas no lineales 0,5/1,5; balances 0,25/0,5;
  regularización 1/100; transiciones 0/0,05.
- Español eligió **lineal**, regularización 1, balance 0,5 y transiciones 0,05.
- Inglés eligió **no lineal, escala 0,5**, regularización 1, balance 0,25 y
  transiciones 0,05.
- JSON del modelo: 48 031 bytes/es y 611 530 bytes/en. El modelo inglés creció;
  falta medir memoria máxima y latencia real en el servidor antes de integrar.
- Los archivos V3/V4 y la prueba visual anterior no se sobrescribieron.

Las clases siguen desequilibradas. Por ejemplo, en español hay 2661 ventanas B
y 91 H; en inglés, 2882 B y 204 H. Son ventanas superpuestas, no tantos ejemplos
independientes. Sigue pendiente la revisión humana de formas y fronteras.

## Nueva prueba de animación

Abrir en navegador `tmp/isa-own-classifier/animation-v5/index.html`.
El panel propio comienza en V5 y permite volver a V3. Rhubarb queda como control
en el otro panel. Se reutilizan exactamente los mismos PCM y textos de la prueba
anterior: el cambio visible proviene de las marcas del nuevo modelo.

El banco de imágenes, selectores, atlas y renderizador permanecen idénticos.
La selección de 24 frames adicionales continúa aparte, sin agregar cientos de
imágenes ni mezclar simultáneamente cambios visuales y acústicos.

## Verificación

- 33 pruebas sintéticas/de integración aprobadas, incluidas separación no lineal
  de grupos XOR, persistencia de predicciones JSON, compatibilidad con modelos
  anteriores y rechazo de configuraciones no finitas.
- Las seis líneas de tiempo finales pasan el validador actual del backend.
- Navegador: ES/EN × V5/V3, audio avanzando, retratos completos, pausa, búsqueda,
  cambio de velocidad/tema, ancho móvil y cero solicitudes HTTP externas.
- Se inspeccionó la captura del ensayo inglés V5.
- No hubo commit, push, cambio de configuración ni despliegue de esta etapa.

## Reproducir

Desde la raíz del backend con los recursos locales anteriores:

```powershell
python experiments/isa_classifier/prepare_next_corpus.py --previous tmp/isa-own-classifier/corpus-v4/corpus.json --additions experiments/isa_classifier/corpus_v5_additions.json --output tmp/isa-own-classifier/corpus-v5
.venv/Scripts/python.exe experiments/isa_classifier/generate_corpus.py --plan tmp/isa-own-classifier/corpus-v5/plan.json --output tmp/isa-own-classifier/corpus-v5
python experiments/isa_classifier/train_next.py --corpus tmp/isa-own-classifier/corpus-v5/corpus.json --previous-corpus tmp/isa-own-classifier/corpus-v3/corpus.json --previous-corpus tmp/isa-own-classifier/corpus-v4/corpus.json --reference-models tmp/isa-own-classifier/v3 --output tmp/isa-own-classifier/v5
.venv/Scripts/python.exe experiments/isa_classifier/prepare_demo.py --output tmp/isa-own-classifier/animation-v5 --versions v5 v3 --reuse-demo tmp/isa-own-classifier/animation-ab
Copy-Item -LiteralPath tmp/isa-own-classifier/animation-ab/extra-frames.html -Destination tmp/isa-own-classifier/animation-v5/extra-frames.html
node experiments/isa_classifier/build_animation_demo.mjs ../app-clima tmp/isa-own-classifier/animation-v5
node experiments/isa_classifier/check_animation_demo.mjs ../app-clima tmp/isa-own-classifier/animation-v5
python -m unittest discover -s experiments/isa_classifier -p test_*.py -q
```
