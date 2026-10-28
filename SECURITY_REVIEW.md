# Revisión de seguridad local — 28 de octubre de 2026

Revisión de código, ataques reproducibles con Django Test Client, pruebas de
navegador con respuestas simuladas y auditoría de dependencias. No es una
certificación ni un pentest independiente. No se atacó el despliegue público,
no se hicieron pruebas de saturación y no se enviaron payloads a proveedores.

## Hallazgos y correcciones

| Hallazgo | Riesgo | Corrección |
| --- | --- | --- |
| Endpoints públicos sin presupuesto de solicitudes | Alto para disponibilidad/costos del hosting | Ventana móvil global por proceso: voz 6/min, clima 30/min, lugares 120/min y alertas 60/min; operación atómica entre hilos y recuperación automática. |
| Voz aceptaba sustitutos Unicode e invisibles | Entradas inválidas llegaban a síntesis | Rechazo 400 antes de iniciar un worker, manteniendo tildes, espacios y saltos de línea válidos. |
| JSON de voz aceptaba claves duplicadas | Interpretación ambigua | Rechazo 400; solo se permite la clave texto. |
| Límite del JSON comprobado tras leer todo el cuerpo | Lectura innecesaria de datos grandes | Lectura acotada a 8193 bytes y rechazo 413 sin parsear ni sintetizar. |
| Consultas HTTP demasiado largas | Trabajo evitable al procesar entradas | Rechazo 414 a partir de 2049 caracteres de query string en rutas de proveedores. |
| Instalador pip local con avisos de vulnerabilidad | Herramienta de instalación desactualizada | Actualizado de 25.3 a 26.2.2; nuevo Build Command documentado para producción y Gunicorn fijado en requirements-production.txt. |
| Cabeceras del frontend sin configuración versionada | Endurecimiento de navegador incompleto | vercel.json añade nosniff, política de referer, restricciones de permisos, bloqueo de embedding y CSP limitada a base/object/ancestors. |

## Controles comprobados

- Coordenadas fuera de rango, parámetros duplicados y desconocidos, métodos y
  tipos de contenido no admitidos, controles Unicode y tamaños de entrada.
- Destinos HTTPS de OpenWeather fijos. Cadenas con URL de metadata, delimitadores
  de query y SQL permanecen como parámetros codificados y no cambian host o clave.
- Los textos de ciudad, descripción y consejo con HTML/onerror se muestran como
  texto en celular, tablet y escritorio; no crean elementos ni ejecutan scripts.
- No hay base de datos, ORM ni ejecución de consultas SQL en esta aplicación.
- Piper recibe texto por stdin sin shell ni rutas/modelos elegidos por el cliente.
- Presupuesto de solicitudes atómico: 20 intentos concurrentes contra un límite
  de 3 admiten exactamente 3; IPs y cabeceras Origin inventadas no aumentan cuota.
- En configuración de producción, 429 conserva CORS y no-store, no inicia otra
  síntesis y mantiene disponible health. DEBUG, hosts, HTTPS y logs seguros están
  cubiertos por las pruebas de producción existentes.
- El contexto de Groq excluye secretos y campos desconocidos, conserva datos en
  JSON y no habilita herramientas. Las respuestas se limitan a 280 caracteres y
  40 palabras. Estas medidas no garantizan que un modelo jamás siga una instrucción
  contenida en datos; limitan su capacidad a producir texto escapado.

## Dependencias

`npm audit`: cero avisos conocidos en el árbol instalado del frontend.
`pip-audit`: cero avisos conocidos tras actualizar pip, sobre 33 paquetes instalados
en el entorno local, incluidas las dependencias de Piper. Se audita además el
archivo de producción para incluir Gunicorn. Los resultados son una foto del
catálogo de avisos disponible, no una garantía de ausencia de fallos.

## Alcance pendiente y limitaciones

- Los cambios deben desplegarse en Render/Vercel para actuar online. Las cabeceras
  de vercel.json aún deben comprobarse en el despliegue nuevo.
- API pública sin cuentas: CORS no es autenticación, y se puede pedir síntesis de
  cualquier texto permitido dentro de la cuota. No se implementó CAPTCHA ni prueba
  firmada que vincule cada audio a un consejo previo.
- Un atacante puede consumir el presupuesto global y afectar temporalmente a
  visitantes legítimos. Se prioriza limitar CPU y consumo de proveedores. Tráfico
  distribuido, saturación de conexiones y volumetría requieren controles del hosting
  o un proxy/CDN; el middleware no puede detener tráfico antes de que llegue a Python.
- El presupuesto se reinicia al reiniciar el proceso. No es compartido entre
  réplicas y aumenta si se agregan workers. No se confía en X-Forwarded-For para
  evitar que un cliente invente IPs; no existe identificación individual de visitantes.
- La CSP añadida no restringe script-src: no se afirma que sea una política CSP
  completa contra XSS. Una política estricta requiere validar las dependencias del
  avatar y los estilos de Angular para conservar su funcionamiento.
- No se auditó el historial Git completo, las cuentas de hosting, DNS/TLS ni sus
  permisos. No se hicieron pruebas autenticadas sobre las consolas de terceros.

## Reproducción

Backend: `.venv\Scripts\python.exe scripts/test_backend.py`.
Frontend: `npm run build`, `npm run e2e:typecheck` y, con el servidor de pruebas
local en 4300, `npx playwright test e2e/security.spec.ts e2e/isabel.spec.ts --grep
"maliciosos|lee el texto exacto"`.

Referencia: [OWASP REST Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html).
