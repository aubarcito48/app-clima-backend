# Protocolo RF V2, congelado antes de sintetizar — 2026-11-17

Entrenar desde cero una versión candidata; conservar RF V1 y todos sus datos.
Reutilizar los textos previos sin mover grupos entre train/dev/test.
Sumar 48 consejos: por idioma 12 train, 4 dev y 8 finales nuevos, con dos
velocidades cuando la reducción se confirma en el PCM. Conservar saludos,
despedidas, fonemas de la misma síntesis y pausas insertadas comprobadas.

Las mejoras del renderer (carga, salida al reposo, autoplay/429) no son ejemplos
acústicos ni convierten etiquetas de imágenes en fonemas correctos.
Evaluar los modelos con la selección visual revisada después de entrenar.

RF: 120 árboles, profundidades 12/20, hojas 3/8, semillas fijas; mismas
características acústicas/temporales/fonéticas y balance de V1. Selección sólo
en dev, con transición 0/0,05 y penalización de cierre 0/0,25. Comparar contra
RF V1 bajo las mismas referencias reparadas. No retocar según test.

Métricas: consejo sin pausas verificadas, promedio por grupo, F1 macro,
cierre incorrecto y recuperación de cierre/silencios. Rhubarb sigue siendo
referencia débil: concordancia no equivale a precisión visual humana.
Las pruebas nuevas finales se excluyen del entrenamiento y de su selección.
No sustituir el sistema publicado ni prometer un porcentaje de mejora.
