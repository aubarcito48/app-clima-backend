# Red temporal pequeña: protocolo fijado antes del entrenamiento

Conservar train/dev y crear ocho consejos finales nuevos por idioma, con variantes
de velocidad agrupadas. Los tests anteriores pasan a históricos. No se selecciona
ningún parámetro con el nuevo test. Saludos y despedidas exactos de la app.

Usar las mismas características acústicas/fonéticas por idioma. Red de retardos
temporales (TDNN mediante MLP): offsets [-12,-8,-4,0,4,8,12] ventanas de ~10 ms,
capas ReLU 64/32, softmax, Adam 0,001, alpha 0,01, batch 512, seed 20261116.
Normalización calculada sólo en train, clipping a ocho desviaciones. No es RNN
ni genera imágenes. Entrenar 32 épocas, checkpoints 8/16/24/32. Por checkpoint
probar penalización de cierre 0/0,25 y transición 0/0,05, igual que los árboles.

Dos brazos predefinidos: pausas reparadas anteriores, y las mismas etiquetas con
ventanas de frontera de pausa comprobada excluidas del gradiente. No asignar
silencios naturales ni fonemas dudosos a X. Un borde dudoso es una ventana de
análisis de 40 ms que intersecta un hueco insertado pero no está enteramente en él.
Se guardan cambios y exclusiones por grabación en un sidecar. Corpus original intacto.

Balance por clase 0,25 ES/0,5 EN, cap 4; consejo peso 1 y saludo/despedida 0,25,
dividiendo por variantes de cada grupo. Transiciones sólo train, sin unir archivos.
No usar partición aleatoria de ventanas para early stopping. Seleccionar en dev:
primero candidatos con falsos cierres <= XGB+0,002, cierre de pausa >= XGB-0,01,
recall A >= XGB-0,03; después F1 macro agrupado y concordancia. Si ninguno pasa,
guardar el mejor F1 sólo para diagnóstico. Comparar ambos brazos y RF/XGB congelados
con la misma referencia de test (sin alterar la métrica para favorecer un brazo).

Métrica primaria consejo, sin saludo/despedida ni pausas insertadas; concordancia
con referencia automática, no precisión visual humana. Medir continuidad, deriva,
saltos y cierres de frames aparte. Visor con mismo audio/reloj, pausas verificadas,
velocidad de voz y aceleración local previas. Mantener producción sin cambios.
