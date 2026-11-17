# Ronda de identidad fonética

Conservar los 139 audios train y 32 dev de la ronda ampliada. Sus test pasan a
evaluación histórica, sin entrar en train/dev. Añadir 16 consejos sólo test,
8 por idioma, con baseline y velocidad automática cuando corresponda.

A las 48 señales anteriores se añade identidad one-hot del fonema/etiqueta
actual. Vocabulario distinto por idioma, derivado exclusivamente de train,
con categorías fijas para pausas insertadas y símbolos desconocidos. Nunca se
amplía con dev/test. Las marcas del Piper existente no son reconocimiento nuevo.

16 candidatos fijos: balance .25/.5, ridge 1/100, no lineal None/.5, transiciones
0/.05. Peso acotado por clase y dividido por variantes de la misma frase. Elegir
en dev por F1 macro agrupado por consejo, desempate por concordancia. Evaluar
una sola vez en las frases nuevas, frente al modelo ampliado congelado y V7.

Se mantienen ajustes automáticos de voz, animación, fonemas, pausas y barras en
la prueba final. No cambiar banco de imágenes ni producción. Etiquetas débiles
Rhubarb y visuales: las puntuaciones no garantizan coordinación percibida.
