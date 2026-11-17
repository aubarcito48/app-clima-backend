# Entrenamiento híbrido fonético, fijado antes de evaluar

- Regenerar las 128 frases de V7 con sus mismos splits: por idioma 40 train,
  8 dev, 16 test. No trasladar frases entre splits. No confundir nuevos renders
  con frases nuevas: la prueba final es una reevaluación exploratoria de frases
  reservadas anteriores, no una prueba externa independiente.
- Audio nuevo para obtener duraciones Piper durante ese mismo pase de síntesis.
  No aplicar duraciones de otra generación al PCM anterior. Saludo/despedida app.
- Entradas: las 36 señales acústicas/temporales, one-hot de visema fonético,
  posición y duración del intervalo. Nunca etiquetas Rhubarb como entrada.
- Objetivo: etiquetas débiles Rhubarb, consejo con peso 1, saludo/despedida .25.
  No implica un aprendizaje validado de fonemas ni anotaciones humanas.
- Selección por F1 macro del consejo dev, desempate concordancia. Barrido fijo:
  escala no lineal None/.5, ridge 1/100, balance .5, transición 0/.05 (8 variantes).
- Comparar híbrido seleccionado, V7 congelado y regla fonética sin entrenar sobre
  el mismo PCM test; medir consejo, cierres falsos y pausas conocidas por separado.
- La animación sigue pasando por el planificador temporal ya probado. El banco
  visual y producción no cambian. La puntuación acústica no mide calidad visual.
- No reajustar con el test. Si pierde, conservar resultados y no promoverlo.
