# App Clima Backend

Backend previsto en Python y Django para resolver una ciudad, obtener clima y pronóstico de OpenWeather y generar una recomendación en español con Groq. El frontend Angular consumirá una única API JSON del backend.

Repositorio: [aubarcito48/app-clima-backend](https://github.com/aubarcito48/app-clima-backend). Frontend: [aubarcito48/app-clima](https://github.com/aubarcito48/app-clima).

## Estado actual

**TK01: documentación local preparada.** Este README concentra la presentación del proyecto, su alcance, planificación y coordinación con Angular. El usuario administra el tablero Kanban; en esta sesión no se publicaron wiki, milestone ni tarjetas en GitHub.

Todavía no se creó el proyecto Django, no se instalaron dependencias ni se implementaron endpoints. La configuración ejecutable empieza en TK02. No hay comandos de arranque o pruebas del backend disponibles aún.

La numeración TK01–TK10 de este repositorio es independiente de la del frontend. En las conversaciones y referencias cruzadas se debe indicar siempre a qué repositorio pertenece cada tarea. Los requisitos e historias del backend usan el prefijo BE.

## Alcance

- Recibir una ciudad obligatoria y filtros opcionales de país o región.
- Resolver ubicación y coordenadas, diferenciando ausencia y ambigüedad.
- Consultar clima actual y los intervalos de pronóstico realmente disponibles.
- Normalizar unidades y fechas, conservando valores ausentes sin inventar datos.
- Pedir a Groq un consejo breve basado en la ubicación y los datos meteorológicos de esa consulta.
- Devolver JSON estable, errores recuperables y disponibilidad parcial por bloque.
- Exponer un health check independiente de los proveedores.

No se incluyen base de datos, ORM, modelos persistentes, migraciones, cuentas, autenticación, sesiones, administrador ni historial funcional de consultas. Los registros operativos previstos se enviarán a consola sin credenciales ni prompts completos.

## Responsabilidades y organización prevista

```text
Angular → Django → OpenWeather
                 → Groq
```

Angular se encarga de la entrada, las consultas HTTP y la presentación. Django valida, resuelve la ubicación, consulta los proveedores, normaliza sus respuestas y protege las claves. El despliegue previsto es Django en Render y Angular en Vercel.

Al crear el proyecto se separarán configuración y rutas, vistas, validadores, esquemas de respuesta y clientes de OpenWeather/Groq. Los destinos externos serán fijos; ciudad, país y región se enviarán como parámetros codificados. La estructura concreta de carpetas y las versiones compatibles se registrarán en TK02.

## Contrato propuesto para acordar en TK03

Esta sección conserva la propuesta de los documentos recibidos. No describe una API implementada ni un contrato probado.

| Método y ruta | Comportamiento previsto |
| --- | --- |
| `GET /api/v1/health/` | Salud de la aplicación sin consultar proveedores ni base de datos. |
| `GET /api/v1/clima/?ciudad=Cordoba&pais=AR` | Ciudad obligatoria, `pais` y `region` opcionales. |

| Bloque de éxito | Campos propuestos |
| --- | --- |
| `ubicacion` | `nombre`, `pais`, `region`, `latitud`, `longitud`, `desplazamiento_horario_segundos`. |
| `actual` | `fecha_utc`, `temperatura_c`, `sensacion_c`, `humedad_pct`, `viento_kmh`, `descripcion`. |
| `pronostico` | `estado` y lista de `intervalos` con `fecha_utc`, `temperatura_c`, `descripcion`. |
| `recomendacion` | `estado` y `texto`, con `null` cuando no esté disponible. |
| `meta` | `fuente_meteorologica`, `consultado_en_utc` y unidades explícitas. |

Las fechas se proponen como ISO 8601 UTC; Angular presentará la hora de la ciudad. Se conservarán temperatura cero o negativa y viento cero. Los campos opcionales ausentes serán `null`; los intervalos no se presentarán como promedios diarios sin un cálculo acordado.

| HTTP | Código propuesto | Situación |
| --- | --- | --- |
| 400 | `ENTRADA_INVALIDA` | Parámetros inválidos; sin llamadas externas. |
| 404 | `CIUDAD_NO_ENCONTRADA` | Sin coincidencias geográficas. |
| 409 | `CIUDAD_AMBIGUA` | Candidatos y posibilidad de precisar país o región. |
| 405 | `METODO_NO_PERMITIDO` | Método no admitido. |
| 429 | `LIMITE_ALCANZADO` | Límite que impide obtener el clima. |
| 503 | `SERVICIO_NO_DISPONIBLE` | Geocodificación o clima temporalmente no disponibles. |

Los errores tendrán `codigo` y `mensaje`. La estructura final de candidatos, validaciones y ejemplos JSON se fijará en backend TK03. No se propagarán credenciales, cuerpos internos ni trazas de proveedores.

Con clima actual válido y falla de Groq se propone HTTP 200 con `recomendacion.estado = no_disponible` y `texto = null`. Si falla solo el pronóstico, se mantendrá el clima y se informará ese bloque como no disponible. Si no hay clima actual válido, no se pedirá a Groq un consejo meteorológico.

## Coordinación con el frontend

| Etapa | Dependencia y entrega |
| --- | --- |
| Frontend TK01–TK04 | Preparación y demo con datos ficticios; no acreditan integración real. |
| Backend TK03 | Acordar contrato y respuestas de ejemplo para preparar tipos y adaptación en frontend TK05. |
| Backend TK07–TK08 | API local integrada y verificada para conectar realmente frontend TK05. |
| Backend TK10 | Publicar en Render y comprobar el consumo desde Angular local. |
| Frontend TK10 | Publicar en Vercel, añadir el origen CORS exacto y verificar la integración pública. |

Frontend TK05 permanece pendiente mientras avanzamos con el backend. Su modelo de demo no se debe asumir como contrato de Django. La región opcional del contrato del backend deberá coordinarse con Angular para resolver ambigüedades que persistan al indicar país.

## Planificación del backend

Milestone propuesto: **Backend — Primer incremento**. Tendrá exactamente las diez tareas siguientes. Estados del Kanban: **Pendiente**, **En curso** y **Terminado**. Las fechas no están definidas; P1–P10 expresa secuencia, no días ni duraciones. Responsable propuesto en los archivos: Nahuel Argandoña.

| ID | Tarea | Dependencias del backend | Tamaño | Pruebas | Estado de referencia local |
| --- | --- | --- | --- | --- | --- |
| TK01 | Definir documentación y organización del backend | Ninguna | S | CP15 | En curso: documentación local lista, tablero a cargo del usuario. |
| TK02 | Configurar Django sin base de datos | TK01 | S | CP01, CP12, CP13 | Pendiente |
| TK03 | Definir contrato JSON y validar las entradas | TK02 | S | CP02, CP03, CP11 | Pendiente |
| TK04 | Resolver ciudades con OpenWeather | TK03 | M | CP04, CP05 | Pendiente |
| TK05 | Consultar y normalizar clima actual y pronóstico | TK04 | M | CP06, CP07, CP10 | Pendiente |
| TK06 | Generar recomendaciones con Groq | TK05 | M | CP08, CP09 | Pendiente |
| TK07 | Integrar el endpoint de clima inteligente | TK03, TK05, TK06 | M | CP09, CP10, CP11 | Pendiente |
| TK08 | Ejecutar pruebas del backend y del contrato | TK07 | M | CP01–CP11, CP15 | Pendiente |
| TK09 | Preparar seguridad y configuración de producción | TK08 | M | CP12, CP13 | Pendiente |
| TK10 | Publicar Django en Render y validar la integración | TK09 y acceso a las cuentas de los proveedores | M | CP12, CP13, CP14, CP15 | Pendiente |

Cada tarjeta conservará objetivo, actividades, aceptación, prioridad, tamaño, responsable, dependencias, requisitos, historias, pruebas y evidencia. Los textos completos están en `Tareas_Backend_App_Clima.md`, entregado en la carpeta de trabajo junto al repositorio; no se duplican en nuevos documentos de este repositorio.

La planificación de referencia recibida también incluye `Documentacion_Backend_App_Clima.docx` y `Planificacion_Backend_App_Clima.xlsx`. Los tres originales se mantienen sin modificaciones, con sus estados iniciales; este README registra el trabajo local posterior.

## Calidad y criterio de cierre

La trazabilidad seguirá **BE-RF/BE-RNF → BE-HU → TK → CP → evidencia**. TK01 se vincula a **BE-RNF04**, **BE-HU06** y **CP15**.

Las pruebas previstas usarán `SimpleTestCase` o `unittest` con proveedores simulados, sin base de datos de pruebas, credenciales reales ni llamadas pagas. CP01–CP11 cubren configuración y comportamiento; CP12–CP13, secretos y CORS; CP14, la integración real en Render; CP15, documentación y trazabilidad.

Una tarjeta se cierra con sus criterios y pruebas aplicables verificados y evidencia real: fecha, entorno, resultado, defecto si corresponde y enlace a commit o PR. Los errores y resultados parciales deben verificarse sin depender del texto exacto de una IA real.

## Credenciales y configuración previstas

Las claves permanecerán en el `.env` local del backend, excluido de Git, o en variables privadas de Render. TK02 preparará `.gitignore`, `.env.example` sin secretos y la lectura de configuración. No se necesitan claves para esta tarea documental.

Variables previstas: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `OPENWEATHER_API_KEY`, `GROQ_API_KEY`, `GROQ_MODEL`, `CORS_ALLOWED_ORIGINS` y ajustes explícitos de espera y reintentos.

Producción tendrá DEBUG desactivado, hosts y orígenes concretos, destinos externos fijos y esperas/reintentos acotados por proveedor. CORS autoriza lectura desde orígenes del navegador; no autentica la API ni establece un límite global de consumo.

## Decisiones pendientes

- Versiones compatibles de Python/Django y dependencias, estructura final y módulo de arranque: TK02. Se detectó Python 3.14.3 local, sin seleccionar todavía la versión del proyecto.
- Contrato definitivo, formato de país/región, validaciones y candidatos de ciudad: TK03.
- Producto meteorológico disponible en OpenWeather: antes de integrar clima y pronóstico.
- Modelo habilitado en Groq, tiempos de espera, reintentos y límites: antes de la integración y publicación.
- Fechas del incremento, URL de Render y origen final de Vercel: pendientes.
- MCP queda como evolución posible; no es una dependencia de esta primera implementación.

## Evidencia local de TK01

24 de octubre de 2026. Entorno: Windows, repositorio `app-clima-backend`, rama `main` al iniciar la tarea.

Se revisaron los tres archivos fuente, el repositorio y su remoto. Se preparó este README con alcance, contrato propuesto, las diez tareas, seguimiento previsto y dependencias con Angular. Se verificó la coherencia de identificadores y títulos del plan recibido.

CP15: revisión documental local realizada; falta registrar y verificar el tablero con sus diez tarjetas y enlaces para completar el criterio de seguimiento. La wiki externa no se publicó: por la preferencia acordada, la documentación se concentra en este README. No se declara CP15 íntegramente aprobado ni TK01 cerrada en el tablero.

CP01–CP14 no ejecutados. No se creó Django, entorno virtual, base de datos, migraciones, endpoints ni despliegue. No se generó commit o PR en esta sesión.
