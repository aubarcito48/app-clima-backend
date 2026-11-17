# Contenido variado, velocidad automática y balanceo · 16/11/2026

Se completó [PROTOCOL-RATE-BALANCE.md](PROTOCOL-RATE-BALANCE.md), conservando
modelos y corpus anteriores. Ningún cambio se integró a producción.

## Corpus

- 231 grabaciones, 1945,72 segundos (32 min 26 s), 184 grupos de consejos.
- Se conservaron las 128 grabaciones anteriores. Se añadieron 56 consejos nuevos,
  28 por idioma, con viento, lluvia, niebla, heladas, humedad, calor y actividades
  cotidianas. Máximo 40 palabras, saludo/despedida y pausas de la app.
- Los 56 consejos produjeron 103 audios: 56 baseline y 47 versiones reducidas
  automáticamente. Sin copias cuando el controlador decide conservar el ritmo.
- Español: 67 train, 16 dev, 12 test nuevos correspondientes a 8 frases.
  Inglés: 72 train, 16 dev, 16 test nuevos correspondientes a 8 frases.
  Los 32 test anteriores se conservan en disco pero no se usan en la selección
  ni en las cifras primarias de esta ronda.
- Variantes baseline/automática nunca cruzan splits. Sus pesos de entrenamiento
  se dividen por el número de variantes y las métricas primarias se promedian por
  grupo de frase. No son 28 frases test independientes: son 16 frases nuevas.

La auditoría verificó PCM únicos, hashes, separación de grupos y los 47 pares:
las frases seleccionadas duran más y las pausas insertadas conservan su longitud.
Cada WAV posee sus propias duraciones Piper y etiquetas débiles Rhubarb.

## Entrenamiento y selección

Híbrido de 48 señales de voz, ritmo y fonética. Se compararon 16 candidatos por
idioma: balance .25/.5, cap 4, ridge 1/100, no lineal None/.5, transición 0/.05.
Selección por F1 macro del consejo agrupado por frase en dev, desempate por
concordancia. Ambos idiomas eligieron balance .5, ridge 1 y transición .05.
Así que **probar otro balance no demostró que hubiera que cambiarlo**.

Todas las clases A–H/X aparecen en train. D sigue siendo mucho menos frecuente
que B/C; ampliar el corpus no elimina el desbalance natural. Los pesos son
acotados para evitar que pocas etiquetas raras dominen el ajuste.

Los modelos nuevos se guardaron en `hybrid-rate-balanced-v1/hybrid-es.json` y
`hybrid-en.json`, bajo `tmp/isa-own-classifier/`.

## Consejos test nuevos: media entre grupos de frases

| Modelo | ES concordancia | ES F1 macro | EN concordancia | EN F1 macro |
| --- | ---: | ---: | ---: | ---: |
| V7 | 60,45 % | 37,86 % | 54,50 % | 44,76 % |
| Híbrido anterior | 58,37 % | 33,74 % | 56,00 % | 45,04 % |
| Nuevo, ampliado y balanceado | 60,75 % | 38,32 % | 55,87 % | 45,60 % |

Frente al híbrido anterior: español +2,38 puntos de concordancia y +4,58 F1;
inglés -0,13 puntos de concordancia y +0,56 F1. Mejora española y cambio pequeño
en inglés; no se alcanzó 80 %, ni se demuestra superioridad visual general.
Las cifras anteriores de otras rondas pertenecen a otras frases/renders.

Referencia: Rhubarb sin revisión humana. No se ajustó después de consultar test.
Ocho grupos por idioma son pocos para afirmar una generalización sólida.
Esta ronda cambia corpus y entrenamiento juntos; no atribuye causalmente la
mejora sólo a la reducción de velocidad ni sólo al balanceo.

## Indicadores secundarios por ventanas

Ventanas de consejo con A/X cuando la referencia pide apertura, con denominador
de todas las ventanas: ES 5,19 % -> 4,68 %; EN 4,69 % -> 4,46 %.
Cierre durante pausas insertadas: ES 80,84 % -> 81,89 %; EN 99,02 % sin cambio.
Estas métricas acústicas tampoco aseguran que el selector muestre esa boca.

Las variantes se reportan separadas en `evaluation.json`. Los test de español
no tienen todos una variante lenta: sólo 4/8 consejos pidieron reducción; inglés
8/8. No comparar medias baseline/automática como si fueran todas las mismas frases.

## Visor completo

`tmp/isa-own-classifier/rate-balance-review-v1/index.html` incluye:

- Ritmo actual y velocidad reducida automáticamente, cada uno con su audio.
- Planificador con aceleración local de cierres, inicialmente activada en inglés
  y perfil español conservado; interruptor para comparar su efecto.
- Clasificador anterior o nuevo seleccionable sin reiniciar el audio.
- Tres muestras por idioma: la anterior y dos consejos test nuevos con ambos ritmos.
- Fonema activo, búsqueda temporal, energía, pausas insertadas, baja energía
  candidata, boca solicitada, frame elegido y control con el modelo anterior.

Los objetivos de velocidad siguen siendo reglas experimentales de dos pasadas,
no una política que aprenda sola durante el uso. El modelo sí se entrenó con
ejemplos de ambos ritmos. No se añadieron imágenes. Las etiquetas visuales siguen
siendo provisionales y la prueba requiere escuchar/ver antes de promover cambios.

## Validación y reproducción

62 pruebas Python, pruebas del planificador y Playwright ES/EN: audio exclusivo,
velocidad real 1×, tiempos propios, cambio de clasificador, acelerar cierres sin
reiniciar, barras pintadas, búsqueda, contenido nuevo, móvil y funcionamiento sin
peticiones externas. La app frontend y producción no se modificaron.

```powershell
.\tmp\isa-phoneme-env\Scripts\python.exe -X utf8 experiments/isa_classifier/generate_rate_expansion.py --previous tmp/isa-own-classifier/corpus-phonetic-v1/corpus.json --output tmp/isa-own-classifier/corpus-rate-nuevo
python experiments/isa_classifier/audit_rate_corpus.py tmp/isa-own-classifier/corpus-rate-nuevo/corpus.json
python experiments/isa_classifier/train_phonetic.py --corpus tmp/isa-own-classifier/corpus-rate-nuevo/corpus.json --baseline tmp/isa-own-classifier/v7 --reference-hybrid tmp/isa-own-classifier/hybrid-phonetic-v1 --rate-expansion --output tmp/isa-own-classifier/rate-models-nuevo
```

Artefactos: `corpus-rate-balance-v1/corpus.json`, `audit.json` y
`hybrid-rate-balanced-v1/evaluation.json`. Usar carpetas nuevas para otras rondas.
