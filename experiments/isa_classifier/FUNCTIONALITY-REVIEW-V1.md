# Prueba integrada antes de entrenar

Abrir [visor completo](../../tmp/isa-own-classifier/functionality-review-v1/index.html).

Seis muestras existentes: lluvia y dos consejos reservados en cada idioma.
Todas conservan saludo y despedida de la app, el PCM previamente generado con
reducción automática por frase, marcas fonéticas y pausas de esa síntesis.
No se generó audio nuevo, no se añadieron frames y no hubo entrenamiento.

- Izquierda: renderer y manifiestos de `cd332da7e76a8c4fc446d4e9f3f1e40fc50e09b6`,
  con selección visual anterior.
- Derecha: renderer local corregido, referencias de cierre corregidas y
  etiquetas de apertura/cierre revisadas. Empalme inglés opcional, desactivado
  de inicio; el español conserva el rango original.
- Ambos lados usan exactamente el mismo audio, RF congelado y reloj absoluto.
  Se muestran energía, pausas insertadas, candidatos de baja energía, forma
  solicitada, frame seleccionado y referencia previa.

## Cómo comparar

1. Elegir Cori/Sharvard y una muestra. Pulsar «Reproducir comparación» a la derecha.
2. Observar especialmente cierres durante la voz y transiciones entre frases.
3. Usar el deslizador para repetir fragmentos; «Detener lectura y ver cierre»
   permite observar el fundido al reposo.
4. «Probar fallo temporal de imágenes» realiza dos lecturas sintéticas sin voz
   sobre retratos nuevos. El primer intento falla intencionalmente; en el segundo,
   el anterior no recupera imágenes y el corregido sí. El resultado se informa y
   los retratos normales se restauran automáticamente. Mantenerlos visibles.

Las recuperaciones de autoplay y HTTP 429 se comprobaron en las pruebas de la
app y backend de la etapa anterior (45/247). El visor local no invoca ni imita
el servicio de Render: su prueba interactiva de fallo actúa sobre imágenes.
No presenta esos escenarios de voz como si fueran solicitudes reales.

La agrupación de marcas inferiores a un frame sigue pendiente. Los consejos
reservados siguen siendo evaluación; revisar un ejemplo no lo convierte en
material de entrenamiento independiente ni demuestra un aumento de precisión.

## Verificación del visor

- Seis muestras reproducidas y buscadas por tiempo; barras pintadas y cierre.
- Ambos modos visuales/idiomas; rangos reales del renderer y frames comprobados
  antes/después del límite de ciclo con el mismo RF/PCM.
- Recuperación real del renderer anterior/corregido en ES/EN, con fallo controlado.
- Sin errores JavaScript ni peticiones de red; pantalla de 390 px sin desborde.
- Pruebas del planificador y política visual correctas.

Resultados locales: `viewer-check.json`, `functional-viewer-check.json`,
`provenance.json` y capturas `complete-es.png`, `complete-en.png`,
`complete-mobile.png`. La procedencia registra hashes del WAV y PCM.

```powershell
node experiments/isa_classifier/prepare_functionality_review.mjs ../app-clima tmp/isa-own-classifier/visual-policy-review-v1 tmp/isa-own-classifier/functionality-review-v1
node experiments/isa_classifier/build_auto_rate_demo.mjs ../app-clima tmp/isa-own-classifier/functionality-review-v1
node experiments/isa_classifier/check_visual_policy_viewer.mjs ../app-clima tmp/isa-own-classifier/functionality-review-v1
node experiments/isa_classifier/check_functionality_review.mjs ../app-clima tmp/isa-own-classifier/functionality-review-v1
```
