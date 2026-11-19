# Isa RF V2 en la ruta publicada

Motor predeterminado: `ISA_LIP_SYNC=own`. El antiguo valor `rhubarb` selecciona
también nuestro motor para facilitar la migración de Render; nunca ejecuta ese
binario. `off` permite volver al audio sin clasificación. Las herramientas y
pruebas históricas de Rhubarb se conservan como referencia fuera de la ruta activa.

El build existente instala `requirements-production.txt` y ejecuta
`python scripts/install_voice.py`. Prepara copias derivadas de las voces con
salida de duraciones, sin modificar los ONNX originales. ONNX se usa al construir,
no se importa durante una petición. No se instala sklearn ni se entrena al iniciar.

Cada petición ejecuta Piper y después un proceso independiente de inferencia RF;
no residen simultáneamente. Límites: 45 s Piper, 30 s RF, audio hasta 90 s. Los
fonemas privados viajan en `isap`, se consumen y eliminan antes de responder.
El WAV público contiene `isac`, `isav` y `isam` con `engine=isa-rf-v2`.
El cliente usa las políticas visuales revisadas para ese identificador y mantiene
la ruta anterior para WAV históricos. No se activa el empalme inglés candidato.

Pesos versionados en `api/services/assistant/alignment/isa_ml/weights/`, exportados sin pickle.
Procedencia y hashes en `provenance.json`. La inferencia sólo necesita NumPy.
Código de inferencia congelado, sin importar archivos de `experiments/` o `tmp/`.

Verificación local: 4 casos comparados con el clasificador experimental producen
idénticas predicciones y PCM, sin filtrar `isap`. 4 síntesis reales ES/EN con
saludo/despedida: Piper 4,0–5,8 s; RF 0,65–0,72 s. Picos individuales Windows:
Piper 168–204 MiB, RF 233–240 MiB; no equivalen a consumo cgroup Linux.
La recuperación de autoplay/ocupación y de imágenes se conserva.

Después de desplegar, comprobar una respuesta real en cada idioma: WAV válido,
`isam` correcto, marcas contiguas y reproducción del cliente. Verificar el estado
del despliegue; un push no prueba por sí mismo que Render terminó de reconstruir.

Reversión: revertir los commits frontend/backend o `ISA_LIP_SYNC=off` y redesplegar.
