# Fase 2: director local de prueba

El modo predeterminado sigue siendo `groq`. No se modifica la boca ni el
renderizador del frontend. Esta etapa implementa reglas deterministas, no un
clasificador entrenado ni reconocimiento de emociones.

## Flujo y compatibilidad

| Modo | Salida solicitada a Groq | Director de actuación |
| --- | --- | --- |
| `groq` | `texto` y `segmentos` | Groq, como hasta ahora |
| `local` | Solo `texto` | Python, sin llamadas adicionales |

Ambos usan una consulta por consejo. Se conservan los datos meteorológicos, el
estilo argentino/inglés, los límites del consejo, las validaciones y el presupuesto
de generación. En local se eliminan las instrucciones y la salida de actuación
del modelo. Esto reduce esa parte del prompt y de la salida solicitada; el ahorro
real debe medirse con `usage` en varias muestras, incluido el razonamiento. No se
garantiza un coste o una latencia menores en cada respuesta.

El plan local conserva exactamente el texto normalizado aprobado. Separa por fin
de frase o punto y coma, nunca por palabra, y limita a cuatro segmentos. Un decimal
como `21.5` no produce una separación. Las reglas actuales son deliberadamente
moderadas:

| Indicio en la frase | Gesto | Velocidad | Volumen | Pausa entre fragmentos |
| --- | --- | --- | --- | --- |
| Sin indicio específico | `isa-awake` | 1 | 1 | 160 ms |
| «evitá», «cuidado», «precaución» / equivalentes ingleses | `isa-down` | 0.96 | 0.96 | 220 ms |
| «después», «más tarde», referencias a tarde/noche / equivalentes ingleses | `isa-right` | 1 | 1 | 180 ms |

La precaución tiene prioridad. El último segmento no añade silencio final. No se
deduce el estado emocional ni se reinterpretan los datos del clima: la detección
es léxica y puede omitir matices. El volumen no cambia la emoción de la voz.

El contrato público sigue siendo `texto` más `segmentos` compatibles. Piper recibe
el mismo plan validado y mantiene su línea de tiempo basada en muestras de audio.
No cambian los límites de voz, las cancelaciones, el saludo ni la despedida del
frontend. El retrato actual conserva el habla continua y la mirada al frente
durante el audio; generar `gesture` no incorpora movimientos nuevos al retrato.
Esta fase tampoco sincroniza fonemas: eso pertenece a la fase 3.

## Probar y volver al director anterior

En `.env` del backend, agregar o cambiar una sola línea:

```dotenv
ISA_DIRECTOR=local
```

Reiniciar Django y generar un consejo nuevo desde el frontend conectado a ese
backend. Cambiar una variable local no modifica Render ni el frontend publicado.
Para volver, usar `ISA_DIRECTOR=groq` y reiniciar. Un valor distinto detiene el
arranque con un error de configuración; no se elige un director silenciosamente.

Comparar español e inglés, consejos de una y dos frases, precauciones y cambios
para más tarde. Revisar inicio, pausa/cancelación y final. Para evaluar solo la
actuación, usar el mismo texto en `direct_locally`; dos generaciones independientes
pueden producir consejos diferentes y no constituyen una comparación controlada.

La suite aislada se ejecuta sin claves, red ni base de datos:

```powershell
.\.venv\Scripts\python.exe scripts/test_backend.py
```

Cubre texto intacto, repetibilidad, reglas bilingües, validación del contrato,
una sola petición, ausencia de reintentos ante una respuesta inválida y entrega
del plan local al servicio de Piper. La revisión perceptual y las mediciones de
voz real/tokens quedan pendientes de la prueba local; no se atribuye un porcentaje
de precisión a estas reglas.
