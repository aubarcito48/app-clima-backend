# Random Forest frente a XGBoost con pausas reparadas

Mismos 139 train / 32 dev, las mismas correcciones fiables de pausas y mismo
vocabulario exclusivamente train. Entradas, contexto temporal y pesos por clase
idénticos al XGBoost reparado: balance .25 ES / .5 EN, cap 4, consejo 1 y
saludo/despedida .25, dividido por variantes del mismo consejo. No mover test a train.

RF: 120 árboles, bootstrap, max_samples .8, max_features sqrt, gini, profundidades
12/20 y min_samples_leaf 3/8; cuatro ajustes por idioma, semilla 20261116, dos hilos.
No usar OOB como prueba independiente: las ventanas vecinas están correlacionadas.
Decodificación compartida: penalización A/X 0/.25 y transición 0/.05, total 16
candidatos/idioma. Elegir sólo en dev por F1 macro agrupado y concordancia,
con los mismos límites de falso cierre, pausas y recall A que la ronda XGBoost.
Si ningún candidato pasa, guardar el mejor F1 como diagnóstico, sin promoverlo.

Nuevo test: 16 consejos, 8 por idioma, baseline y automático sólo si se verifica
reducción real. Evaluar RF y XGBoost congelado sobre idéntico PCM/máscaras,
excluyendo de la métrica principal los silencios insertados confirmados.
Medir aparte pausas completas/interiores y planes visuales; etiquetas restantes
siguen siendo débiles Rhubarb, no calidad humana. No reajustar con test.

Guardar RF como arrays NumPy comprimidos (allow_pickle=False) y verificar
probabilidades frente al predictor nativo antes de usar la exportación.
El visor conserva voz automática, aceleración de animación y barras.
No cambiar producción ni banco visual. Red temporal queda para la siguiente etapa.
