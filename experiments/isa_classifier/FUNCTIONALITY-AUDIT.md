# Auditoría funcional de Isa — 2026-11-17

Actualización: ver [correcciones posteriores](FUNCTIONALITY-FIXES-V1.md).
Este informe conserva los hallazgos y evidencias previos a esas correcciones.

Revisión local de 25 funciones del avatar y su cadena de voz con prosody-lens,
audio-lens, animatorsSurvivalKit e image-eye-checker. No se modificaron servicios
ni componentes de producción, ni se entrenó o desplegó un modelo.

Informe navegable: [abrir evidencias](../../tmp/isa-own-classifier/functionality-audit-v1/index.html).
El inventario completo y el estado de cada función están en `functionality.json`
del mismo directorio. Se separan funciones de producción y experimentales.

## Hallazgos prioritarios

1. **Recuperación de atlas:** el renderer conserva los fallos de decodificación
   en `speechFailed`. Al desaparecer un fallo transitorio, otra lectura en el
   mismo idioma no vuelve a cargar la página. Cambiar de idioma sí recupera la
   animación. Reproducido con el renderer real y un fallo de imagen controlado.
   Próxima corrección: reintento acotado por lectura, preservando el fallback.
2. **Cierre al terminar:** el manifiesto español declara el frame 123 como boca
   cerrada, pero la revisión visual lo considera abierto; 128 sigue incierto.
   El renderer puede usar 123 como destino de cierre. La mezcla cae a 0,316 a
   los 100 ms, de modo que esto no demuestra un salto visual grave. Unificar
   las referencias revisadas también para esta salida, primero en laboratorio.
3. **Resolución temporal:** en los consejos RF evaluados, 198/891 intervalos
   españoles (22,22 %) y 118/675 ingleses (17,48 %) duran menos de 41,67 ms,
   un frame a 24 FPS. El selector no puede representar cada cambio por separado.
   Probar agrupación contextual y coarticulación, preservando cierres breves;
   no imponer un mínimo uniforme que borre consonantes importantes.
4. **Recuperación de voz:** falta una acción explícita para repetir un audio
   bloqueado por autoplay. Silenciar y reactivar no repite el consejo por diseño.
   El backend devuelve 429/Retry-After cuando está ocupado; la interfaz muestra
   un error genérico. Evaluar reintento acotado y mensajes diferenciados.

## Qué se verificó

- Backend: **246 pruebas**, retorno 0; frontend: **38 pruebas en 12 archivos**.
- Renderer real en Chromium: **15 comprobaciones**, incluyendo poses,
  parpadeo, ambos idiomas, prioridad frontal al hablar, salida al reposo,
  movimiento reducido, visibilidad simulada, fallo de imágenes y destrucción.
- Planner de producción: 32 grabaciones finales, sin retrocesos ni valores
  inválidos. Ajustes locales máximos del reloj: ES −157/+148 ms y EN
  −307/+208 ms aproximadamente. No son medidas de latencia de red ni de
  precisión perceptiva.
- Diez comprobaciones de normalización: grados, singular/negativo y km/h,
  en ambos idiomas. `90.°` llega a voz como `90 grados` / `90 degrees`.
- Dos informes adicionales de prosodia con pausa mínima de 60 ms: los
  candidatos pasan de 1 a 13 en una muestra ES y de 3 a 6 en una EN frente
  al umbral anterior de 250 ms. Son candidatos acústicos, no etiquetas ciertas.
- Se extrajeron sin escalar las regiones originales de las 34 bocas inciertas.
  Los videos conservaron sus hashes. Se mantienen inciertas: no se añadió
  contenido al banco ni se sustituyeron etiquetas por conjeturas.

## Límites y siguiente etapa

El RF, los fonemas internos de Piper, la reducción automática de velocidad y
las políticas visuales revisadas siguen siendo experimentales. La ruta de
producción acepta Rhubarb opcional según configuración; no se inspeccionó la
configuración efectiva de Render/Vercel. La visibilidad se simuló en navegador:
no es una prueba de suspensión real en móviles.

La revisión anterior conserva 374 etiquetas binarias revisadas y 34 inciertas;
no son un conjunto de verdad humana independiente. La concordancia con Rhubarb
no equivale a porcentaje de sincronización visual. Estos resultados no permiten
prometer un 80 % o 100 % ni aprobar por sí solos una salida a producción.

Orden propuesto: recuperar atlas y revisar anclas de cierre; después evaluar
secuencias cortas con audio fijo y revisión perceptiva ciega por idioma. Mantener
saludos, despedidas, reloj absoluto, límites de salto y referencias de control.

## Reproducción

Desde el backend:

```powershell
node experiments/isa_classifier/audit_runtime_playback.mjs ../app-clima tmp/isa-own-classifier/corpus-tdnn-v1/corpus.json tmp/isa-own-classifier/functionality-audit-v1
node experiments/isa_classifier/build_functionality_harness.mjs ../app-clima tmp/isa-own-classifier/functionality-audit-v1
node experiments/isa_classifier/check_functionality_harness.mjs ../app-clima tmp/isa-own-classifier/functionality-audit-v1
python experiments/isa_classifier/build_functionality_report.py tmp/isa-own-classifier/functionality-audit-v1
node experiments/isa_classifier/check_skill_audit_index.mjs ../app-clima tmp/isa-own-classifier/functionality-audit-v1
```

Los análisis de audio, ojos y regiones nativas usan el entorno aislado ya
documentado en [SKILLS-AUDIT.md](SKILLS-AUDIT.md), sin servicios externos.
