# Correcciones funcionales de Isa — 2026-11-17

Implementación local basada en [FUNCTIONALITY-AUDIT.md](FUNCTIONALITY-AUDIT.md).
Sin despliegue ni reentrenamiento. Se conservaron los informes anteriores;
las nuevas evidencias están en `tmp/isa-own-classifier/functionality-fixes-v1/`.

## Implementado

- **Imágenes:** limpiar fallos al empezar otra narración permite recuperar
  recursos del mismo idioma. Se conserva la caché y el retrato de respaldo;
  los fallos siguen suprimidos dentro de cada narración, sin reintento por RAF.
  Chromium comprobó dos cargas de recuperación y mezcla de habla 1; antes,
  la segunda lectura tenía cero reintentos y mezcla 0.
- **Cierre ES:** retirados 123 (abierto) y 128 (incierto) del manifiesto y sus
  fuentes 135/140 de la configuración generadora. No se inventaron cierres ni
  se cambió el selector durante el habla. Se conserva el fundido inmediato y
  el avance máximo de seis frames. Desde 120, el destino ahora es el límite
  126 en lugar del falso cierre 123; 126 es un límite, no una boca certificada
  como cerrada. La mezcla a 100 ms sigue siendo 0,316.
- **Autoplay:** «Reproducir audio» llama directamente a `play()` sobre el mismo
  audio preparado mediante un clic, sin otra síntesis ni consulta a Groq.
- **Ocupación:** un 429 permite un solo reintento automático respetando
  `Retry-After` en segundos o fecha HTTP. Sin cabecera espera cinco segundos.
  Una espera superior a 30 segundos o inválida queda para acción explícita;
  no se adelanta la indicada. El segundo fallo muestra estado ocupado.
  Otros errores no se reintentan automáticamente. Silenciar, cambiar consejo
  o idioma y destruir la vista cancelan las esperas y resultados viejos.
- **Acción explícita:** errores y ocupación persistente ofrecen «Reintentar
  voz» para el consejo vigente. Mensajes y botones tienen traducción EN.
  Reactivar después de silenciar sigue sin repetir el consejo automáticamente.
- **CORS:** el backend expone `Retry-After` para los orígenes ya autorizados,
  necesario para que Vercel lea la espera de Render. No se ampliaron orígenes.

## Verificación

45 pruebas Angular de Isa en 12 archivos y compilación de producción correctas.
15 comprobaciones del retrato real en Chromium: recuperación, cierre ES,
poses, reloj, movimiento reducido, visibilidad simulada y destrucción.
247 pruebas backend correctas, incluida cabecera CORS legible y origen no permitido.
No se modificaron audios, bancos visuales ni modelos de aprendizaje.

Reproducción del retrato corregido, desde el backend:

```powershell
node experiments/isa_classifier/build_functionality_harness.mjs ../app-clima tmp/isa-own-classifier/functionality-fixes-v1
node experiments/isa_classifier/check_functionality_harness.mjs ../app-clima tmp/isa-own-classifier/functionality-fixes-v1 --expect-fixes
```

## Pendiente experimental

La agrupación contextual de marcas menores que un frame requiere comparación
perceptiva con audio fijo, conservando consonantes y pausas. No se activó un
mínimo uniforme que borre sonidos. Las 34 bocas inciertas siguen inciertas;
RF y red temporal siguen en laboratorio. Estas correcciones no cambian sus
puntuaciones ni prueban el funcionamiento efectivo del despliegue remoto.
