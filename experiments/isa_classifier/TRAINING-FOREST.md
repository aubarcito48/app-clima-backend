# Random Forest frente a XGBoost · 16 de noviembre de 2026

Random Forest mejora modestamente la concordancia en esta prueba reservada,
pero todavía no justifica reemplazar el sistema publicado. El candidato español
no supera todos los controles de validación. Inglés sí los supera.

## Comparación controlada

Se conserva el protocolo previo a los resultados en [PROTOCOL-FOREST.md](PROTOCOL-FOREST.md).
Ambas familias reciben las mismas señales acústicas, fonemas de Piper, contexto
temporal, pesos por clase y correcciones verificadas de pausas. Se utilizan
139 grabaciones para entrenamiento y 32 para validación, sin mover frases entre
conjuntos. Las variantes de velocidad de un consejo permanecen juntas.

La prueba final agrega 16 consejos nunca usados para seleccionar parámetros:
8 por idioma, cada uno con versión original y velocidad automática. Son 32
grabaciones finales. Saludo y despedida reproducen los de la app. La métrica
principal evalúa solamente el consejo, excluye las pausas insertadas verificadas
y promedia por frase para no contar las dos velocidades como consejos distintos.
El corpus archivado completo reúne 354 grabaciones, aproximadamente 51 minutos.

Se ajustaron cuatro bosques por idioma: 120 árboles, profundidad 12/20 y mínimo
de muestras por hoja 3/8; además, cuatro combinaciones de decodificación temporal.
La selección utiliza validación exclusivamente. El conjunto final se abre después
de congelar la selección, sin retocar parámetros según sus resultados.

## Resultados sobre los consejos nuevos

Las referencias son etiquetas automáticas de Rhubarb corregidas sólo en el
interior seguro de pausas insertadas. Esto mide concordancia con esa referencia,
no un porcentaje de calidad visual ni precisión humana de fonemas.

| Idioma | Concordancia XGBoost | Concordancia RF | F1 macro XGBoost | F1 macro RF |
| --- | ---: | ---: | ---: | ---: |
| Español | 61,80 % | 63,69 % | 37,60 % | 40,69 % |
| Inglés | 61,14 % | 63,14 % | 51,13 % | 52,67 % |

Sólo hay ocho grupos finales por idioma: esta diferencia requiere más evaluación
independiente antes de considerarla una ventaja general.

Español selecciona profundidad 20, hoja 3 y transición 0,05, como candidato de
diagnóstico: ninguno de los 16 candidatos pasa todos los controles. Su recuperación
de A en validación baja de 49,87 % a 44,13 %, por debajo de la tolerancia de tres
puntos; el cierre en pausas baja de 82,10 % a 80,95 %, también fuera de tolerancia.
Los cierres incorrectos durante apertura sí bajan de 3,66 % a 2,89 %.
Inglés selecciona profundidad 20, hoja 8 y transición 0,05, con controles aprobados.
Ambos usan penalización de cierre cero y balance previo (0,25 ES / 0,5 EN).

En las pausas interiores del consejo final no hay mejora: ambos alcanzan
100 % en español y 97,92 % en inglés. Incluyendo bordes, español empeora ligeramente.
Estos porcentajes describen las clases predichas, no el cierre del avatar.

## Animación y automatizaciones

La auditoría ejecuta 128 planes: 32 audios, dos modelos, con/sin aceleración local.
Se conservan límites de continuidad, pose y avance monotónico. En inglés, la
aceleración reduce el indicador provisional de cierre visual durante habla en
15 de 16 grabaciones para cada modelo, sin incrementarlo en ninguna:
RF pasa de 7.792 a 2.042 ms acumulados; XGBoost de 8.042 a 2.125 ms.
Español mantiene la aceleración desactivada por defecto y no cambia este indicador.

La boca del frame sigue sin cerrar siempre cuando la clase pide pausa:
RF cierra en 68/128 instantes españoles (igual que XGBoost) y 79/123 ingleses
(XGBoost: 78/123). El mapeo visual es provisional y necesita revisión humana.
Mejorar el clasificador no elimina por sí solo los errores del selector de frames.

Pruebas locales:

- `tmp/isa-own-classifier/forest-direct-v1/index.html`: izquierda XGBoost, derecha
  RF; exactamente el mismo audio con velocidad automática, un reloj, ambos
  retratos simultáneos y barras alineadas. Incluye consejos nuevos en ES/EN.
- `tmp/isa-own-classifier/forest-review-v1/index.html`: comparación original frente
  a velocidad automática, selección de modelo y decisiones por frase.

La velocidad de voz sigue siendo una regla experimental por frase, no una política
aprendida por el bosque. Se regenera voz y fonemas cuando se reduce la velocidad;
el reproductor queda en 1×. Se preservan los ajustes independientes por idioma.

## Verificación y límites prácticos

Los bosques se exportan como arrays comprimidos NPZ, sin pickle; la inferencia
portable coincide con probabilidades nativas de sklearn con tolerancia 1e-12.
Los JSON finales pesan aproximadamente 21,5 MB ES y 15,4 MB EN: son más grandes
que XGBoost y falta medir latencia/memoria en el entorno de despliegue.
scikit-learn 1.9.1 se instala sólo en el entorno experimental; no se cambia runtime.

Pasan los verificadores de ambos visores: audio, reproducción simultánea, reloj,
seeking, barras, cambio de idioma/muestra, móvil y funcionamiento sin red.
Pasan los cuatro tests del bosque portable y los cuatro de XGBoost en el entorno
experimental; la suite general ejecuta 79 casos con un salto dependiente de XGBoost,
cubierto mediante esa ejecución aislada. Se inspeccionan capturas de los visores.

Artefactos: `forest-v1/evaluation.json`, `forest-pause-audit-v1/`,
`forest-v1/pause-roles.json` y `forest-visual-v1/visual-evaluation.json`, todos bajo
`tmp/isa-own-classifier/`. En el reporte heredado, `boosted` identifica al bosque
nuevo e `identity` al XGBoost reparado; `model_names` explicita esta correspondencia.

No se modifica producción, Rhubarb ni el banco publicado. Se conservan audios,
modelos y pruebas anteriores. Antes de promover un modelo conviene corregir
fronteras y etiquetas visuales revisadas por una persona, y evaluar nuevos grupos.
