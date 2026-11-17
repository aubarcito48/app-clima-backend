# Primero calidad de pausas; después comparación de familias

Conservar PCM, Rhubarb original y corpus previos. Sólo relabelar como X el
interior de pausas insertadas con procedencia isac/phoneme-gaps del mismo PCM,
verificación de muestras exactamente cero y soporte completo de la ventana
acústica de 40 ms dentro del intervalo. No convertir baja energía, puntuación,
silencios naturales ambiguos ni consonantes en etiquetas ciertas de pausa.

Los gaps de 20/80 ms entre chunks sólo se aceptan si coinciden con el generador;
los segmentos requieren metadata isac consistente. Verificar hash del audio
original de síntesis. Las etiquetas originales se guardan sin alteración y las
correcciones se registran como sidecar/transformación reproducible.

Comparación controlada: reentrenar XGBoost con las configuraciones congeladas de
boosted-v1, una por idioma, y la misma semilla/rondas/features/pesos de enfoque.
Cambiar sólo etiquetas seguras y los pesos por clase/transiciones que derivan de
ellas. Mantener 139 train / 32 dev; el vocabulario se obtiene sólo de train.
No buscar nuevos parámetros a partir de resultados test. Evaluar 16 consejos
nuevos, exclusivamente test, con variantes actual/auto válidas.

La métrica primaria compara habla del consejo excluyendo todas las pausas
insertadas verificadas, para que acertar silencio conocido no infle el porcentaje.
Evaluar aparte cierre A/X y reposo X: pausa completa, interior de 40 ms y pausas
de segmento tradicionales. Recalcular ambas versiones del modelo sobre idéntico
PCM y las mismas máscaras. No forzar X en la predicción para presentar un 100 %.

Las fronteras naturales ambiguas y la mayor parte de las etiquetas siguen siendo
débiles. Mantener las automatizaciones de voz/animación y sus barras. Comprobar
planes visuales aparte. No cambiar producción. Random Forest y red temporal
quedan para después de esta primera etapa y no se usan para mezclar efectos.
