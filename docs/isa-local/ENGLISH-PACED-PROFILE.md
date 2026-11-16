# Perfil inglés pausado v1 — ensayo local

El director inglés expone `direct_english(text, profile='paced-v1')` para una
comparación explícita. La interfaz de la app sigue usando `baseline`; no se
activa el perfil al iniciar Django ni se altera el director español.

El ensayo conserva el texto y los gestos existentes. Ajusta la velocidad por
longitud de fragmento: 0,90 para doce o más palabras, 0,92 para ocho o más y
0,96 para fragmentos cortos. Estos umbrales son heurísticos y requieren revisión.
La energía se conserva. Propone 90 ms tras punto y coma, 120 ms tras final de
oración y cero tras el último fragmento. Busca evitar sumar una pausa fija grande
al silencio que Piper ya produce por puntuación. No inserta pausas por palabra.

Se usa la misma Cori base, con factor de síntesis 1,08 dividido por la velocidad
del segmento. No se apilan las variantes anteriores 1,20 o 1,30 sobre este plan.
Piper genera un WAV nuevo y Rhubarb analiza ese WAV; no se trasladan tiempos de
otra grabación. Se exportan el plan y la línea `isac` medida por el worker para
comprobar que las decisiones de dirección llegan efectivamente a la voz.

El reloj experimental del HTML combina pausas acústicas con las pausas medidas
del director y fusiona sus solapamientos. No suma dos retenciones sobre el mismo
intervalo. La actuación continúa usando cuadros completos; no implica control
independiente de la boca ni precisión por palabra.

Los archivos de prueba, el generador y las muestras se conservan en el frontend
en `docs/isa-local/cori-english-director-v1` y
`scripts/synthesize-isa-english-director.py`. No requiere otra llamada a Groq.
El ensayo se conserva en el repositorio; guardarlo no activa el perfil pausado.

## Corrección independiente de pronunciación de grados

La normalización previa a Piper ahora reconoce `90.°`, `90°`, `25.°C` y
`25. °C`, además de los formatos de Celsius anteriores. Produce `90 grados`
en español y `90 degrees` en inglés. Conserva decimales, signos, singular/plural
y la puntuación final; no cambia el texto mostrado en la app. El ordinal `1.º`
y la unidad inmediata `°F` no se reinterpretan como Celsius.

El separador de fragmentos evita cortar entre el valor `25.` y la unidad `°C`.
Esto corrige un caso de formato, no modifica las velocidades o gestos españoles.
Las pruebas del perfil, independencia entre idiomas y grados pasan en la suite
de 238 tests. También se generaron audios locales reales de Sharvard y Cori
en `tmp/isa-pronunciation` para revisión auditiva del usuario.
