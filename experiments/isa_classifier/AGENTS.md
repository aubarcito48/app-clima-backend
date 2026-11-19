# Preferencias de las pruebas de Isa

- Toda nueva muestra de voz debe reproducir el saludo y la despedida de la app:
  español «¡Buenas, explorador!» / «¡Hasta luego, explorador!»;
  inglés «Hello, explorer!» / «See you later, explorer!».
- Usar `narration.app_performance` y contrastar sus frases y pausas con
  `../app-clima/src/app/service/assistant/voice/isabel-voice.ts`. Los consejos son cortos,
  como los de Groq: máximo 40 palabras y 280 caracteres en el consejo central.
- El saludo tiene pausa de 160 ms y la despedida de 0 ms, como la app.
- Medir por separado el consejo para que las frases repetidas no inflen las métricas.
- Conservar los experimentos históricos sin sobrescribirlos. Sus audios sin
  saludo/despedida sirven sólo de referencias anteriores; no imitarlos al crear muestras nuevas.
- No ampliar indiscriminadamente el banco de imágenes: elegir pocos frames útiles,
  descartar casi duplicados y comprobar pose/continuidad antes de incorporarlos.
- No modificar producción ni sustituir Rhubarb por una buena puntuación automática
  sin una comparación visual y pruebas con datos reservados.
