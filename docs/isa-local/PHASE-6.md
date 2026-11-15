# Prueba 6: comparar directores con un consejo fijo

No cambia la configuración del backend ni producción. La dirección local sigue
configurada como antes. Es un experimento aislado para comparar planes y voz,
no una medición del costo promedio ni de precisión de sincronización labial.

Desde el backend, con sus dependencias, voces y credencial local ya configuradas:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/compare_isa_directors.py
```

Se envía a Groq solamente un consejo ficticio aprobado. Se usa el modelo de la
configuración local, el contrato actual de segmentos, su catálogo de gestos y
límites. Se añade una instrucción para preservar exactamente el consejo; no se
realiza otra generación de texto meteorológico. Se permite una petición sin
reintentos automáticos. La salida se valida contra el texto exacto y el contrato
existente. El plan local se obtiene con `direct_locally` sin ninguna petición.

Los planes, consumo informado y WAV se guardan en `tmp/isa-directors-6/`.
Si ya existe el plan, se reutiliza sin consultar otra vez a Groq. Los WAV válidos
también se reutilizan por hash. No se imprimen claves ni errores crudos del
proveedor. El primer intento dentro del entorno restringido falló por conexión;
la ejecución autorizada con acceso a red completó una petición real con consumo.

El mismo worker de Piper sintetiza ambos planes secuencialmente, con el mismo
modelo y speaker. Rhubarb se desactiva únicamente mediante `override_settings`
en este proceso de comparación; no se cambia `.env`. Los WAV conservan sus
tiempos reales `isac`. No se fija una semilla: las diferencias entre las voces
no pueden atribuirse exclusivamente al plan en una sola muestra.

## Resultado guardado el 15 de noviembre de 2026

Consejo común:

> Usá una campera liviana por el viento. Más tarde puede llover; evitá el calzado abierto y llevá un paraguas.

El director local produjo tres segmentos: neutral, mirada derecha y precaución
con mirada abajo. Groq produjo dos: neutral y una mirada derecha para toda la
segunda frase, con velocidad 0,95, volumen 0,9 y 400 ms de silencio final.
Los controles cambian ritmo, volumen y pausas; no generan una nueva emoción vocal.

La petición real a `openai/gpt-oss-20b` informó 940 tokens de entrada y 220 de
salida, total 1160. La salida incluye 95 tokens de razonamiento; no sumarlos otra
vez. La latencia del cliente fue 0,984 s en esta ejecución. No interpretar ese
total como costo extra fijo por consejo ni ahorro promedio de producción: esta
petición de dirección con texto fijo no equivale al flujo completo de generación
de consejo más dirección que usa la app en modo Groq.

El audio local duró 6,551 s y el de Groq 6,994 s, incluyendo pausas. Los tiempos de
síntesis no son un benchmark controlado: hubo ejecuciones secuenciales y posibles
efectos de calentamiento. La diferencia de duración tampoco indica cuál es mejor.

## HTML de revisión

Desde el frontend:

```powershell
node scripts/preview-isa-directors.mjs
node scripts/check-isa-directors-preview.mjs
```

Abrir `clima/app-clima/tmp/isa-mouth-preview/index-6.html` con Live Server o
directamente en un navegador. Es autónomo: contiene WAV y atlas y no hace
peticiones a Groq al abrirlo o reproducirlo.

Se reutiliza el código actual de `isa-portrait.ts`, `isa-motion.ts` y
`models/isa-performance.ts`, transpilado solo para este HTML. **El componente
actual fuerza actuación frontal mientras habla**: las miradas solicitadas por
los planes se muestran en tablas, pero no se presentan como ejecutadas. El
reloj ponderado por velocidad de segmentos y el cierre de habla son los reales.
La comparación conserva el material continuo original al que volvió la 5B;
no incorpora nuevos cortes por Rhubarb ni las tomas 2/3.

La revisión compara una voz por vez, evita superposición, muestra el segmento
activo, consumo y duraciones, y exporta el informe con `reviewed: false`.
La comprobación verifica texto exacto, metadatos reales de audio, reproducción,
pausa, fin, exclusión de voces simultáneas, exportación, vista móvil y ausencia
de red desde el HTML. Los hashes confirman conservación de recursos y pruebas.
La preferencia perceptual de Nahuel sigue pendiente; no se cambió el director
de producción, ni se hizo commit o push de esta prueba.
