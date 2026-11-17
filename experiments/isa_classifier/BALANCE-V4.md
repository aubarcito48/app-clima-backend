# Prueba de balanceo V4 · 16/11/2026

Resultado: **no se promueve V4**. El balance moderado ayudó en desarrollo, pero
el candidato seleccionado no superó a V3 en F1 macro sobre las frases nuevas
reservadas. Se conservan ambos resultados, sin sustituir el modelo de referencia.
Ninguno de los prototipos se ha integrado a producción.

## Protocolo fijado antes de evaluar

- Plan versionado: `corpus_balance_v4.json`, 32 grabaciones y 147,22 segundos.
- Reutiliza únicamente las doce grabaciones de entrenamiento de V3.
- Veinte audios nuevos: ocho de entrenamiento, seis de desarrollo, seis de prueba.
- Por idioma: diez grabaciones de entrenamiento, tres de desarrollo y tres de prueba.
- El cargador rechaza PCM duplicado y comprueba que las frases y PCM de desarrollo
  y prueba no hayan aparecido en ninguna partición de la ronda anterior.
- Cinco exponentes de balanceo: 0; 0,25; 0,5; 0,75; 1. Cada uno compara dos niveles
  de regularización y tres fuerzas de transición: treinta candidatos por idioma.
- El peso de clase se limita a cuatro **antes** de normalizar los pesos a media uno.
  La normalización permite comparar la regularización entre alternativas.
- Selección por F1 macro combinado de las tres grabaciones de desarrollo;
  concordancia media por grabación sólo como desempate. No se selecciona con prueba.
- En prueba se evalúan sólo el ganador de desarrollo, el control sin balanceo
  elegido en desarrollo y el V3 congelado. No se prueban todos los exponentes
  sobre el conjunto final para elegir el que dé el porcentaje más alto.

La referencia sigue siendo Rhubarb, sin corrección humana. Los resultados miden
concordancia con sus marcas y no precisión fonética o calidad visual real.

## Resultado final en las mismas seis grabaciones nuevas

| Modelo | Español: concordancia | Español: F1 macro | Inglés: concordancia | Inglés: F1 macro |
| --- | ---: | ---: | ---: | ---: |
| V3 congelado | 41,4 % | **19,8 %** | **56,9 %** | **48,1 %** |
| Nuevo, sin balanceo | **49,0 %** | 15,3 % | 53,2 % | 33,9 % |
| Nuevo, balance elegido en desarrollo | 43,8 % | 17,5 % | 55,7 % | 40,1 % |

La concordancia es media por grabación. F1 macro se calcula por clase a partir
de todas las ventanas de prueba; combina precisión y recall, dando el mismo
peso a las formas frecuentes y raras. Un clasificador que dice casi siempre B
puede subir la concordancia y seguir fallando en las formas menos frecuentes.

Los anteriores 53,9 %/60,0 % de V3 se obtuvieron en otras grabaciones; no se
comparan directamente con 43,8 %/55,7 %. La fila V3 de esta tabla vuelve a
evaluar **el mismo modelo congelado** sobre las mismas frases nuevas que V4.

## Qué mostró el balanceo en desarrollo

| Exponente | Español: F1 macro | Inglés: F1 macro |
| --- | ---: | ---: |
| 0 | 35,6 % | 35,1 % |
| 0,25 | 38,1 % | **42,0 %** |
| 0,5 | **40,7 %** | 41,6 % |
| 0,75 | 37,0 % | 41,1 % |
| 1 | 33,7 % | 36,9 % |

Cada fila usa su configuración de regularización/transición elegida sólo en
desarrollo. Más balanceo no garantiza mejor reconocimiento: las clases escasas
también contienen pocos ejemplos, fronteras dudosas y contextos limitados.

## Cobertura y errores

Ventanas superpuestas de entrenamiento, no observaciones independientes:

| Forma | Español | Inglés |
| --- | ---: | ---: |
| A | 424 | 331 |
| B | 1621 | 1912 |
| C | 1427 | 798 |
| D | 90 | 149 |
| E | 105 | 127 |
| F | 358 | 268 |
| G | 228 | 374 |
| H | 56 | 130 |
| X | 161 | 573 |

Se amplió la cobertura de las clases raras respecto de V3, pero no quedó un
corpus equilibrado. El modelo español confunde especialmente B→C (176 ventanas),
C→B (94) y B→G (70). El inglés confunde C→B (138), E→B (77) y F→B (73).
D y H tienen recall cero en ambas evaluaciones; español también falla en E y X.
Estos datos justifican revisar ejemplos y etiquetas antes de aumentar pesos otra vez.

## Decisión y trabajo pendiente

No se modifica el modelo V3 ni se reajusta V4 mirando las etiquetas de prueba.
El conjunto V4 ya fue observado: una próxima selección necesita otras grabaciones
reservadas. No hay evidencia para esperar cerca de 100 % todavía.

Prioridad: revisar los intervalos D/E/H/X y las confusiones B/C, incorporar más
ejemplos independientes y comparar un modelo no lineal en una nueva ronda.
Además, la validación visual debe incluir cierres y transiciones, no sólo cifras
por ventana. Las equivalencias que usa el selector de frames no deben ocultar
errores agrupando etiquetas únicamente para inflar el porcentaje.

Pasaron veinticinco pruebas sintéticas/de integración, incluidas pruebas que
demuestran que 99 % de concordancia puede coexistir con cero reconocimiento
de una clase rara. Se corrigió un fallo transitorio de reemplazo atómico del
manifiesto en Windows mediante reintentos acotados, conservando escritura atómica.

## Reproducir

Desde el backend, con las dependencias y recursos locales de las rondas anteriores:

```powershell
.venv/Scripts/python.exe experiments/isa_classifier/generate_corpus.py --plan experiments/isa_classifier/corpus_balance_v4.json --output tmp/isa-own-classifier/corpus-v4
python experiments/isa_classifier/train_balance.py --corpus tmp/isa-own-classifier/corpus-v4/corpus.json --previous-corpus tmp/isa-own-classifier/corpus-v3/corpus.json --previous-models tmp/isa-own-classifier/v3 --output tmp/isa-own-classifier/v4
python -m unittest discover -s experiments/isa_classifier -p test_*.py -v
```

La ejecución actual reutilizó los doce WAV de entrenamiento V3 comprobados por
hash. En un clon nuevo, el generador puede sintetizar las 32 frases; los resultados
exactos pueden depender de versiones locales. No hubo llamadas a APIs externas.
