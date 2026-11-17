# Protocolo V7 · corpus ampliado y señales temporales

Objetivo: evaluar si más grabaciones y señales de ritmo/energía mejoran la
clasificación, sin confundirla con el ajuste visual de velocidad local.

## Datos fijados antes de entrenar

- 128 grabaciones: sólo 32 reutilizadas del entrenamiento V6 y 96 nuevas.
- Por idioma: 40 entrenamiento, 8 desarrollo y **16 prueba**, frente a 4 pruebas
  por idioma en V6. Los consejos nuevos están en `build_expanded_plan.py`.
- Todas incluyen saludo/consejo/despedida y sus pausas reales, como la app.
- No se reutilizan desarrollo/prueba anteriores para entrenar. Se contrastan
  frases reservadas y PCM con V3/V4/V5/V6; se rechazan duplicados exactos.
- La métrica principal excluye saludo/despedida. El peso de pérdida sigue siendo
  1 para consejo y 0,25 para las frases repetidas, normalizado a media uno.
- Etiquetas débiles de Rhubarb; no se presentan como revisión humana.

## Comparación fijada

1. V6 congelado.
2. Mejor modelo de señales acústicas originales entrenado con el corpus ampliado.
3. Ganador de desarrollo entre señales originales y señales temporales ampliadas.

Se exploran 48 configuraciones por idioma: dos perfiles de señales × tres variantes
lineal/no lineal × dos balances × dos regularizaciones × dos fuerzas de transición.
Se elige por F1 macro del consejo de desarrollo, con concordancia como desempate.
No se eligen parámetros ni se reentrena usando prueba. Si el perfil nuevo pierde
en desarrollo, se conserva la alternativa original; no se fuerza una mejora.

`rhythm_features.py` agrega diez canales a los 26 originales: energía relativa,
baja energía candidata, duración transcurrida/restante de ese tramo y de actividad,
cambios de energía, cambio espectral y densidad de arranques de actividad.
Se calculan sólo desde PCM; no reciben texto, marcas Rhubarb ni etiquetas de prueba.
Usan contexto futuro porque el WAV completo ya existe antes de animar; no es una
implementación de reconocimiento en streaming.

No constituyen límites verificados de palabra u oración. Las versiones anteriores
siguen usando exactamente sus 26 señales, con selección explícita del perfil en
inferencia para impedir mezclar modelos de dimensiones distintas.

## Resultados que se deben informar

- Concordancia media por grabación y F1 macro sobre consejo, en las mismas frases.
- Resultados por clase, confusiones y cantidad de grabaciones que mejoran frente a V6.
- Narración completa como resultado secundario.
- Tasa acústica de cierres cuando la referencia pide apertura, separada del error visual.
- Auditoría visual aparte: V6/V7, con/sin aceleración local bajo límites de pose,
  usando el mismo banco. No convertir sus alertas heurísticas en precisión.
- Mantener el ajuste español desactivado por defecto y no tocar producción.

Ningún resultado acredita 80 % por anticipado. Las etiquetas humanas y la
comparación visual siguen pendientes aunque mejore la concordancia con Rhubarb.
