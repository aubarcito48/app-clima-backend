# App Clima Backend

Backend en Python y Django, en preparación para resolver una ciudad, obtener clima y pronóstico de OpenWeather y generar una recomendación en español con Groq. El frontend Angular consumirá una única API JSON del backend.

Repositorio: [aubarcito48/app-clima-backend](https://github.com/aubarcito48/app-clima-backend). Frontend: [aubarcito48/app-clima](https://github.com/aubarcito48/app-clima).

## Estado actual

**TK02: configuración base implementada y verificada.** Django inicia sin base de datos, con configuración local/producción, credenciales por entorno y CORS explícito para Angular local. El usuario administra el tablero Kanban.

Todavía no se implementaron endpoints de salud o clima ni llamadas a OpenWeather/Groq. Los endpoints empiezan en TK03. Con DEBUG true y rutas todavía vacías, Django muestra su página de bienvenida con HTTP 200; con DEBUG false, una ruta inexistente devuelve 404. La bienvenida no es un health check ni una respuesta de la API.

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

La configuración y las rutas están separadas de la aplicación `api`. Las vistas, validadores, esquemas de respuesta y clientes de OpenWeather/Groq se implementarán en las tareas correspondientes. Los destinos externos serán fijos; ciudad, país y región se enviarán como parámetros codificados.

## Versiones e instalación local

Configuración verificada con Python 3.14.3, Django 5.2.18 LTS, django-cors-headers 4.9.0 y python-dotenv 1.2.4. `requirements.txt` fija también las dependencias transitivas. La [compatibilidad oficial de Django 5.2](https://docs.djangoproject.com/en/5.2/faq/install/) incluye Python 3.14 desde Django 5.2.8.

Desde `app-clima-backend`, en PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe scripts/create_local_env.py
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

No hace falta activar el entorno virtual: los comandos usan su intérprete directamente. El script crea `.env` a partir de `.env.example`, genera un secreto aleatorio de Django sin mostrarlo y conserva intacto un `.env` que ya exista.

No ejecutar `migrate` ni `makemigrations`: este proyecto no usa persistencia. El comando local `runserver` conserva las comprobaciones de Django y omite exclusivamente la revisión de migraciones. `DATABASES = {}` deja el backend dummy de Django, sin conexión a SQLite u otra BD.

## Organización implementada

```text
config/settings/base.py          Ajustes comunes, carga de .env y ausencia de BD
config/settings/development.py   Ajustes locales y orígenes de Angular
config/settings/production.py    DEBUG desactivado, hosts explícitos y validación del secreto
config/settings/environment.py   Parseo de booleanos, listas y secreto obligatorio
config/urls.py                   Prefijo /api/v1/ reservado para la API
config/wsgi.py                   Entrada WSGI; producción por defecto
config/asgi.py                   Entrada ASGI; producción por defecto
api/urls.py                      Rutas vacías hasta TK03
api/views.py                     Vistas reservadas para TK03
api/management/commands/         runserver sin comprobación de migraciones
api/tests.py                     Pruebas de configuración sin base de datos
scripts/create_local_env.py      Preparación segura del .env local
```

`manage.py` usa `config.settings.development` por defecto. WSGI/ASGI usan `config.settings.production` salvo que se establezca explícitamente `DJANGO_SETTINGS_MODULE`. La instalación del servidor de producción y los comandos de Render quedan para TK10.

## Configuración por entorno

`.env` se lee con `python-dotenv`, sin sobrescribir las variables del sistema o de Render. `.env`, sus variantes, `.venv`, cachés y archivos SQLite quedan excluidos de Git; `.env.example` sí se versiona sin secretos.

| Variable | Uso en TK02 |
| --- | --- |
| `DJANGO_SECRET_KEY` | Obligatoria. Secreto privado generado para desarrollo; producción requiere uno robusto y no admite el prefijo inseguro de Django. |
| `DJANGO_DEBUG` | Booleano explícito. Local admite true/false; producción rechaza true. |
| `DJANGO_ALLOWED_HOSTS` | Hosts separados por comas. Local: localhost, 127.0.0.1 y [::1]. Producción exige hosts explícitos sin `*`. |
| `CORS_ALLOWED_ORIGINS` | Orígenes separados por comas. Local: http://localhost:4200 y http://127.0.0.1:4200. |
| `OPENWEATHER_API_KEY`, `GROQ_API_KEY`, `GROQ_MODEL` | Vacíos y opcionales hasta integrar los proveedores. Nunca se envían a Angular. |

El middleware CORS se aplica a `/api/`, admite GET/OPTIONS y no habilita credenciales de navegador ni comodines. Un origen ajeno no recibe `Access-Control-Allow-Origin`. Esto habilita lectura en el navegador; no autentica la API ni bloquea clientes que no usan CORS. [Configuración de django-cors-headers](https://github.com/adamchainz/django-cors-headers#setup).

Para comprobar el entorno de producción se deben preparar sus variables y ejecutar `python manage.py check --settings=config.settings.production`. El `.env` local creado usa `DJANGO_DEBUG=true`, por lo que se debe reemplazar o sobrescribir esa variable con false antes de esa comprobación. En Render se configurarán un secreto propio y los hosts/orígenes reales. La revisión completa de seguridad y el despliegue pertenecen a TK09–TK10.

## Pruebas locales

```powershell
.venv\Scripts\python.exe manage.py test --verbosity 2
.venv\Scripts\python.exe -m pip check
```

Las pruebas usan `SimpleTestCase`, no crean una BD de pruebas ni llaman a proveedores. Los casos de producción se ejecutan en procesos aislados con valores ficticios de prueba; no modifican el `.env` real ni necesitan API keys.

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
| TK02 | Configurar Django sin base de datos | TK01 | S | CP01, CP12, CP13 | Implementación local verificada; evidencia al final del README. |
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

Las claves permanecerán en el `.env` local del backend, excluido de Git, o en variables privadas de Render. TK02 incluye `.gitignore`, `.env.example` sin secretos y la lectura de configuración. No se necesitan claves de proveedores para iniciar la base ni ejecutar sus pruebas.

Variables previstas: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `OPENWEATHER_API_KEY`, `GROQ_API_KEY`, `GROQ_MODEL`, `CORS_ALLOWED_ORIGINS` y ajustes explícitos de espera y reintentos.

Producción tendrá DEBUG desactivado, hosts y orígenes concretos, destinos externos fijos y esperas/reintentos acotados por proveedor. CORS autoriza lectura desde orígenes del navegador; no autentica la API ni establece un límite global de consumo.

## Decisiones pendientes

- Servidor y comando final de producción en Render: TK10. La base local usa Python 3.14.3, Django 5.2.18 y los módulos `config.wsgi`/`config.asgi`.
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

## Evidencia local de TK02

24 de octubre de 2026. Entorno: Windows, Python 3.14.3 y dependencias fijadas en `requirements.txt`. Esta sección actualiza el estado posterior al registro histórico de TK01.

- CP01: `manage.py check` sin incidencias; arranque real en http://127.0.0.1:8000; 16 pruebas aprobadas con omisión de la base de datos de pruebas. Se comprobó la ausencia de modelos, apps de persistencia, carpeta de migraciones y `db.sqlite3`. Se bloqueó la apertura de conexiones durante las comprobaciones y solicitudes de prueba.
- CP12, alcance de TK02: `.env` ignorado y no versionado, plantilla sin secretos, generador local que no sobrescribe el archivo existente, secreto obligatorio y producción que rechaza DEBUG true, hosts vacíos/comodines y secreto vacío. La revisión de clientes externos, logs y despliegue queda para TK09–TK10.
- CP13, alcance de TK02: origen Angular localhost y 127.0.0.1 autorizados, origen ajeno sin autorización de lectura y preflight GET con HTTP 200. Verificado con test client y solicitudes HTTP reales al servidor local.
- `pip check` sin dependencias incompatibles. No se instalaron clientes de OpenWeather/Groq ni servidor de producción.

La ruta usada para comprobar CORS aún no está implementada: el test client con DEBUG false recibió 404 y el servidor local con DEBUG true mostró la bienvenida de Django con 200. No se implementó health, clima ni el contrato de TK03. No se ejecutaron migraciones, no se modificó el frontend y no se generó commit, PR ni despliegue.
