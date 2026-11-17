# Etiquetas binarias y empalme: comparación local fijada antes de medir

Usar Random Forest congelado y los mismos 32 WAV finales anteriores. No entrenar
ni sintetizar nuevo audio. Revisar visualmente contactos del atlas completo por
idioma: abierto, cerrado o incierto. Mantener la forma fina original cuando no
hay contradicción; usar `?` para abierto sin forma fina verificable en vez de
inventar un fonema. Procedencia: inspección del agente, no anotación humana.

Comparar tres políticas: catálogo/rango anterior; etiquetas revisadas con rango
anterior; etiquetas revisadas más empalme inglés candidato. ES conserva el rango.
Las ventanas dudosas quedan fuera de las métricas pareadas de apertura/cierre.
Misma referencia binaria revisada para puntuar ambos lados, denominador pareado.
Medir cierres en habla con apertura pedida y cierres en pausas PCM comprobadas.
No comparar esta puntuación visual con la concordancia RF/Rhubarb del 64 %.

Empalme: búsqueda sólo sobre imágenes, sin puntuar audios. Mínimo seis segundos
de secuencia original hacia adelante, evitando cola inactiva larga y cortes
durante parpadeos. Exigir menor diferencia facial y no mayor discontinuidad de
velocidad que el empalme viejo, apertura compatible y diferencia mandibular <=.02.
Inspeccionar los mejores candidatos. Score cara + .25 velocidad; luego mayor
duración. Guardar la búsqueda, rangos, índices y pruebas de rechazo de un empalme
sin verificar o aplicado al rango equivocado. No afirmar que una reducción
fotométrica pequeña elimina el salto perceptual.

Costes nuevos sólo con catálogo revisado: abierto sin forma fina cuesta .5 ante
petición abierta; cerrado confirmado se penaliza durante habla activa incluso
si ES mantiene desactivada la aceleración extra. Resto de parámetros congelados.
No ampliar deriva ni límites de pose/movimiento. Preservar saltos hacia adelante,
suavizado temporal y reloj absoluto. Al repetir un ciclo nuevo verificar su
frontera además de saltos de 2+ frames. No alterar ni borrar imágenes publicadas.

Visor un audio/reloj, mismos RF/fonemas en ambos retratos y barras. Cada retrato
debe usar efectivamente su propio rango en el renderer, no sólo en las barras.
Control de reproducción, seeking, ciclo, ES/EN, móvil y errores de consola/red.
Ronda de evaluación del selector en datos ya vistos: diagnóstico, no test nuevo
para justificar producción. Las secuencias cortas con ramificaciones son la
etapa siguiente después de comprobar estas referencias y fronteras.
