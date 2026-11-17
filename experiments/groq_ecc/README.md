# ECC como buenas prácticas para Groq — evaluación del 17/11/2026

No se instaló ECC ni se modificó producción. Se probaron sus patrones de ahorro
como hipótesis, manteniendo el modelo configurado `openai/gpt-oss-20b`, el mismo
presupuesto de salida y las opciones de razonamiento actuales. No se probó un
modelo menor. Protocolo: [PROTOCOL.md](PROTOCOL.md).

Se completaron 22 llamadas reales: 16 para comparar cuatro climas en ES/EN,
cuatro repeticiones para observar caché de prefijos y dos llamadas de una prueba
de caché completa con cuatro consultas lógicas. Hubo además un HTTP 429; se
conservaron las respuestas exitosas y se continuó espaciando llamadas 22 s.

| Comparación emparejada (8 por modo) | Actual, director Groq | Director local, mismo modelo |
| --- | ---: | ---: |
| Tokens de entrada | 8216 | 6312 |
| Tokens de salida, incluido razonamiento | 2761 | 1197 |
| Respuestas aceptadas por el parser | 8/8 | 7/8 |
| Mediana por llamada | 0,794 s | 0,621 s |

El modo local reduce 23,2 % la entrada y 31,6 % los tokens totales en esta muestra.
No es un porcentaje de ahorro monetario. La tanda es pequeña y no demuestra
ventaja general de latencia ni equivalencia de calidad. En el consejo frío ES
local apareció «sin abrigo ni chaqueta, porque hace frío» con 3 °C: contradicción
y vocabulario que incumple el estilo solicitado. El modo actual también tuvo
mensajes cuestionables y dos respuestas rechazadas en las repeticiones extra.
No se eligen resultados favorables mediante reintentos ni se cambia el director.

La caché completa de la prueba mantuvo contexto, idioma y parámetros idénticos,
con TTL de 300 s: cuatro consultas lógicas usaron dos llamadas, dos aciertos.
Ambas respuestas almacenadas eran válidas para el parser y se reutilizó su texto
sin regenerarlo. Es un escenario construido para repetir; no mide el porcentaje
de consultas repetidas de usuarios reales. En producción habría que cachear sólo
respuestas válidas, invalidar por cambios de contexto y acotar tamaño/vigencia.

Groq informó además aciertos en su caché nativa sin que instaláramos ECC.
La medición de tokens, la caché y la selección de director son prácticas que
podemos implementar directamente. No se justifica instalar todo ECC para esto.
Recomendación: conservar modelo/director actuales; priorizar medición y caché
de respuestas repetidas sin alterar el contenido ni su vigencia meteorológica.

Informe y mensajes reales: `tmp/groq-ecc-benchmark-v1/index.html`.
Datos: `results.json`, `summary.json`, `report.md`, en el mismo directorio.
No contienen claves ni conversaciones personales: sólo entradas meteorológicas
sintéticas y las respuestas generadas para el experimento.

Fuentes revisadas:
- [Patrones cost-aware de ECC](https://github.com/affaan-m/ECC/blob/main/skills/cost-aware-llm-pipeline/SKILL.md).
- [Caché automática de Groq](https://console.groq.com/docs/prompt-caching).

`benchmark.py` realiza solicitudes reales y tiene un límite explícito de uso.
No repetirlo para abrir un resultado más favorable. `report.py` regenera el
informe sin hacer llamadas de red. El experimento no es una integración de ECC
como dependencia ni un cambio de la aplicación publicada.
