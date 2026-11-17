# V6 · consejos breves con saludo y despedida · 16/11/2026

Se generaron **48 audios nuevos**, 24 por idioma. Todos usan la estructura actual
de la app: saludo + consejo corto + despedida.

| Idioma | Saludo | Despedida |
| --- | --- | --- |
| Español | ¡Buenas, explorador! | ¡Hasta luego, explorador! |
| Inglés | Hello, explorer! | See you later, explorer! |

Saludo y despedida conservan la actuación neutral de la app, con pausas de
160 ms y 0 ms respectivamente. El consejo usa el director local por idioma.
Una prueba contrasta las frases y pausas con `isabel-voice.ts` del frontend.
La preferencia permanente queda registrada en `AGENTS.md` del experimento.

## Corpus y protocolo

- 16 grabaciones de entrenamiento, 4 de desarrollo y 4 de prueba por idioma.
- Consejos de dos frases, máximo 17 palabras/94 caracteres en español y
  18 palabras/93 caracteres en inglés: inferiores a los límites de Groq, 40/280.
- 397,63 s de narración completa, incluidos 228,83 s de consejo hablado.
- Corpus nuevo con este perfil; los audios antiguos sin saludo no se mezclan.
- Frases/PCM reservados se contrastan con V3/V4/V5 para impedir reutilización.
- Etiquetas **Rhubarb sin revisión humana**; ninguna llamada a Groq/OpenWeather.

Se comparan las mismas 24 configuraciones de V5. La selección usa F1 macro
**sólo del consejo de desarrollo**, delimitado por los tiempos reales `isac`
de Piper. Se excluyen saludo, despedida y pausas finales de segmentos.
En entrenamiento el consejo pesa 1 y los tramos repetidos 0,25, seguido de
normalización a media uno. Esta regla se fijó antes de evaluar.

Una prueba comprueba que acertar todas las frases repetidas y fallar todo el
consejo produce **0 % de concordancia del consejo**, evitando inflar el resultado.

## Resultados sobre los mismos consejos finales nuevos

| Modelo | Español: concordancia | Español: F1 macro | Inglés: concordancia | Inglés: F1 macro |
| --- | ---: | ---: | ---: | ---: |
| V3 congelado | 47,7 % | 24,5 % | 53,4 % | 35,7 % |
| V5 congelado | 52,5 % | 23,0 % | **57,5 %** | 41,9 % |
| **V6** | **55,8 %** | **31,0 %** | 57,3 % | **46,3 %** |

Concordancia: media por grabación. F1 macro: por clase combinando las ventanas
del consejo. Frente a V5, V6 mejora F1 en ambos idiomas; la concordancia inglesa
queda prácticamente igual (-0,14 puntos). Sólo hay cuatro grabaciones finales
por idioma: no demuestra generalización ni cercanía a 80 %.

La concordancia de narración completa V6 fue 56,6 %/es y 55,5 %/en, como resultado
secundario. Los porcentajes de otras rondas corresponden a otros audios; la tabla
compara los mismos consejos y voces entre modelos. No se reajustó mirando prueba.

## Modelos y prueba visual

Español eligió modelo lineal, regularización 100, balance 0,5 y sin transiciones;
JSON de 48 534 bytes. Inglés eligió no lineal, escala 1,5, regularización 1,
balance 0,5 y transiciones 0,05; JSON de 605 287 bytes. Falta medir memoria/latencia
en el servidor y revisar etiquetas antes de integrar al endpoint.

Abrir `tmp/isa-own-classifier/animation-v6/index.html` en navegador: permite
alternar V6/V5/V3 contra Rhubarb, con saludo, consejo y despedida. Ambos retratos
comparten exactamente el mismo PCM. Se conservan las demos anteriores.

**Límite real del selector español:** conserva los ciclos completos del video.
En esta muestra todos los motores generan el mismo plan visual español aunque
sus marcas acústicas difieran. La página lo advierte: esa coincidencia no permite
afirmar que el clasificador igualó a Rhubarb. Las métricas superiores se calculan
con marcas acústicas, independientemente de ese selector. El ensayo inglés sí
genera planes visuales distintos. No se modifica el selector aprobado.

Se mantiene el banco actual y la selección aparte de 24 candidatos; no se agregan
imágenes masivamente. Pasaron **40 pruebas**, las ocho líneas de tiempo finales
pasaron el validador actual y el navegador verificó ES/EN × V6/V5/V3, textos con
saludo/despedida, audio, retratos, pausa, búsqueda, velocidad, tema y ancho móvil,
sin solicitudes HTTP externas. No hubo commit, push ni despliegue.

## Reproducir desde el backend

```powershell
python experiments/isa_classifier/build_short_plan.py --output tmp/isa-own-classifier/corpus-v6/plan.json
.venv/Scripts/python.exe experiments/isa_classifier/generate_corpus.py --plan tmp/isa-own-classifier/corpus-v6/plan.json --output tmp/isa-own-classifier/corpus-v6
python experiments/isa_classifier/train_short.py --corpus tmp/isa-own-classifier/corpus-v6/corpus.json --previous-corpus tmp/isa-own-classifier/corpus-v3/corpus.json --previous-corpus tmp/isa-own-classifier/corpus-v4/corpus.json --previous-corpus tmp/isa-own-classifier/corpus-v5/corpus.json --reference-v3 tmp/isa-own-classifier/v3 --reference-v5 tmp/isa-own-classifier/v5 --output tmp/isa-own-classifier/v6
.venv/Scripts/python.exe experiments/isa_classifier/prepare_demo.py --output tmp/isa-own-classifier/animation-v6 --versions v6 v5 v3
Copy-Item -LiteralPath tmp/isa-own-classifier/animation-ab/extra-frames.html -Destination tmp/isa-own-classifier/animation-v6/extra-frames.html
node experiments/isa_classifier/build_animation_demo.mjs ../app-clima tmp/isa-own-classifier/animation-v6
node experiments/isa_classifier/check_animation_demo.mjs ../app-clima tmp/isa-own-classifier/animation-v6
python -m unittest discover -s experiments/isa_classifier -p test_*.py -q
```

Los comandos de demos sin saludo/despedida corresponden a revisiones históricas.
El generador actual exige una carpeta nueva si el texto hablado no coincide,
para no reutilizar silenciosamente un audio con otra descripción.
