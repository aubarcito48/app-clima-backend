# Control de uso de Groq

## Comportamiento

- Máximo inicial: **200 intentos nuevos por día UTC** para toda la aplicación,
  compartido entre procesos que usan el mismo archivo SQLite. No es por visitante.
- Cada intento reserva cupo mediante una transacción antes de construir el cliente.
  Errores HTTP, respuestas inválidas, timeouts y procesos interrumpidos consumen cupo.
  No se devuelve la reserva ni se reintenta automáticamente.
- Consejos ya validados: caché de 300 segundos. Clave SHA-256 sobre mensajes completos,
  idioma, modelo, director, límite de salida y versión. Cambiar clima o prompt invalida
  la clave. No se cachean consejos inválidos como éxitos.
- Una reserva pendiente impide duplicar llamadas simultáneas iguales. El segundo
  visitante recibe clima sin IA mientras termina la primera; puede reutilizar la caché
  en una consulta posterior. Una reserva abandonada expira a los 120 segundos.
- Errores tienen un enfriamiento por clave de 30 segundos para evitar martillar Groq.
- Máximo 512 claves activas. Con la caché llena no se evictan reservas ni se abre
  una llamada adicional. Las entradas vencidas se eliminan en la siguiente consulta.
- Si el cupo se agota, una caché válida sigue disponible. Si falta el archivo, está
  bloqueado o falla, se retorna `recomendacion: {estado: no_disponible, texto: null}`.
  La orquestación conserva el clima actual y pronóstico, sin cambiar el contrato HTTP.
  El frontend ya presenta ese estado sin intentar leer consejos anteriores.

## Configuración

```dotenv
# Ejemplo exclusivamente si /var/data es un disco persistente YA contratado/montado:
GROQ_BUDGET_PATH=/var/data/stitchweather/groq.sqlite3
GROQ_DAILY_REQUEST_LIMIT=200
GROQ_CACHE_TTL_SECONDS=300
GROQ_CACHE_MAX_ENTRIES=512
API_TRUSTED_PROXY_HOPS=0
```

En producción el guard es obligatorio. Si `GROQ_BUDGET_PATH` está vacío o ausente,
la IA no llama a Groq; el servicio meteorológico sigue funcionando. **No desplegar
esperando IA activa sin preparar primero ese almacenamiento.** En desarrollo, sin
variable, el archivo predeterminado está en `.runtime/groq.sqlite3` (ignorado por Git).
Un valor vacío explícito también desactiva llamadas en desarrollo.

SQLite usa la biblioteca estándar: no añade dependencias ni un servicio contratado.
El directorio debe ser privado del usuario del servicio y el mismo para todos los
workers. No sirve un filesystem efímero ni archivos separados por réplica. En Render,
la documentación exige un servicio pago para adjuntar un disco persistente; **esta
implementación no lo contrata**. Si se quieren varias réplicas, hace falta migrar el
almacén a un servicio compartido con operaciones atómicas; no copiar el archivo.

Poner el cupo en `0` detiene intentos nuevos, conservando consejos válidos cacheados.
No borrar el archivo para reiniciar el servidor: se perdería el cupo consumido.
Conservarlo en despliegues. El contador cambia solo al avanzar de día UTC; retroceder
el reloj no concede otro cupo. La caché y las pausas dependen del reloj del servidor.

Se guardan hashes, consejo validado, vencimiento y el contador del día. No se guardan
claves, prompts, consultas libres ni IPs en disco. No hay endpoint público para
reiniciar o modificar el presupuesto. No se registran cuerpos ni credenciales.

## Límites por visitante

Antes de consumir el límite global del proceso se aplica un máximo móvil de 60 s:

| Ruta | Por visitante/minuto | Global/minuto predeterminado |
| --- | ---: | ---: |
| clima | 6 | 30 |
| lugares | 40 | 120 |
| alertas | 20 | 60 |
| voz | 3 | 6 |

Respuesta `429`, `Retry-After` y `Cache-Control: no-store`. Health queda fuera.
Se usa la IP de conexión, normalizada y convertida en HMAC con `SECRET_KEY`; IPv6
comparte cupo por /64. Los visitantes detrás de una misma IP pública comparten cupo.
Hasta 4096 claves ruta/visitante en memoria por proceso; al llenarse se rechazan
claves nuevas hasta liberar entradas vencidas. Los rechazos por visitante no gastan
el cupo global de solicitudes ni alcanzan los proveedores.

`X-Forwarded-For` se ignora por defecto. Detrás de un proxy, verificar su cadena y
que añada/sobrescriba la IP real, y cerrar el acceso directo al servidor; solo entonces
configurar `API_TRUSTED_PROXY_HOPS` con el número de proxies confiables. Se cuenta
desde la derecha, nunca desde el primer valor enviado por el cliente. Configurarlo
sin verificar permite evasión; dejarlo en 0 detrás de un proxy puede agrupar usuarios
en una sola IP. Esa verificación del hosting queda pendiente antes del despliegue.

Los límites por minuto son por proceso y se reinician con él; no son la garantía
financiera. Un bot distribuido puede consumir el cupo diario de IA y afectar su
disponibilidad, aunque no puede superar las reservas del archivo compartido. No se
afirma protección total frente a DDoS ni cobertura de costos de OpenWeather, voz,
ancho de banda, Vercel o Render. Verificar también los planes y límites de esas cuentas.

## Validación y operación

`python scripts/test_backend.py --verbosity 0` prueba sin red y con una carpeta
temporal aislada para este contador. Incluye concurrencia, cupo tras recrear el almacén,
cambio de día, reloj hacia atrás, caducidad de caché, separación por clima/idioma/modelo,
errores consumidos, almacenamiento roto, modo degradado y aislamiento por visitante.
No se usó la clave real ni se generaron llamadas facturables para estas pruebas.

Antes de desplegar: verificar plan Groq y límites del proveedor, persistencia del archivo
y cadena real de proxies. El límite es de **intentos**, no de dólares ni tokens; se
conservan los límites existentes de contexto/salida. Otros proyectos o claves de la
misma organización Groq no pasan por este contador. No modificar precios/modelos
asumiendo que 200 consultas siempre cuestan lo mismo.

Referencias: [discos de Render](https://render.com/docs/disks),
[X-Forwarded-For](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/X-Forwarded-For),
[límites de Groq](https://console.groq.com/docs/rate-limits).
