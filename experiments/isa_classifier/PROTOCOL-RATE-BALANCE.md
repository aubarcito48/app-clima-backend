# Ampliación con velocidad automática y balanceo

Protocolo fijado antes de generar/evaluar. Conservar las 128 grabaciones híbridas
con sus splits. Añadir 56 consejos nuevos (28 por idioma: 16 train, 4 dev, 8 test),
distintos de todo consejo anterior. Cada consejo genera baseline y, si la regla
automática solicita reducir velocidad, una versión automática. Ninguna variante
de una frase puede cambiar de split ni contar como una frase independiente.
No generar copias idénticas cuando todos los factores sean 1.

Entrenar el híbrido de 48 señales, con balance .25/.5 y cap 4; ridge 1/100,
no lineal None/.5, transición 0/.05: 16 candidatos fijos por idioma. Elegir por F1
macro dev del consejo agrupado por frase y concordancia como desempate. Mantener peso del consejo 1,
saludo/despedida .25. Las marcas proceden de la misma síntesis de cada WAV.
Dividir el peso de entrenamiento de cada frase por su número de variantes para
que añadir un render no duplique automáticamente su importancia. Calcular la
métrica primaria como media entre grupos de frases; las variantes no suman
observaciones independientes. Mantener métricas agrupadas por ventanas como secundarias.

Evaluación primaria: sólo los 8 consejos nuevos de test por idioma y sus variantes
agrupadas, comparando el nuevo modelo, híbrido anterior y V7 sobre idéntico PCM.
Informar también cada variante por separado. Test anterior no se usa para seleccionar.
Etiquetas Rhubarb y visuales siguen siendo débiles: no equivalen a calidad humana.
Los objetivos de velocidad siguen siendo una regla experimental, no una política
que aprenda a modificarse sola en producción.

La prueba final debe incluir voz normal/automática, animación recalculada para
cada WAV, modelos anterior/nuevo seleccionables, fonemas, energía y pausas. No
cambiar producción ni banco de imágenes por los resultados de esta ronda.
