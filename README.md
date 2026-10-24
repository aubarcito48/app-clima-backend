# App Clima Backend

Backend en Python y Django, en preparación para resolver una ciudad, obtener clima y pronóstico de OpenWeather y generar una recomendación en español con Groq. El frontend Angular consumirá una única API JSON del backend.

Repositorio: [aubarcito48/app-clima-backend](https://github.com/aubarcito48/app-clima-backend). Frontend: [aubarcito48/app-clima](https://github.com/aubarcito48/app-clima).

## Estado actual

**TK03: contrato v1, validación de entradas y health implementados.** Django opera sin base de datos, con configuración local/producción, credenciales por entorno y CORS explícito para Angular local. El usuario administra el tablero Kanban.

`GET /api/v1/health/` responde 200 con `{"estado":"ok"}`. `GET /api/v1/clima/` valida los parámetros: una entrada inválida devuelve 400 y una válida devuelve por ahora 503, porque la integración con los proveedores empieza en las tareas siguientes. No se devuelve clima inventado ni se consulta OpenWeather/Groq.

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
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe scripts/create_local_env.py
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

No hace falta activar el entorno virtual: los comandos usan su intérprete directamente. El script crea `.env` a partir de `.env.example`, genera un secreto aleatorio de Django sin mostrarlo y conserva intacto un `.env` que ya exista.

`requirements-dev.txt` incluye las dependencias de ejecución de `requirements.txt` y las de validación del contrato para las pruebas. Un entorno que solo ejecute el servicio puede instalar únicamente `requirements.txt`.

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
api/urls.py                      Rutas health y clima
api/views.py                     Health y validación previa a la futura integración
api/validation.py                Formulario y consulta normalizada sin persistencia
api/responses.py                 JSON uniforme y control de método GET
api/contracts/                   JSON Schema v1 y ejemplos ficticios versionados
api/management/commands/         runserver sin comprobación de migraciones
api/tests.py                     Pruebas de configuración sin base de datos
api/test_contract.py             Pruebas de entradas, HTTP y esquema JSON
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

Las pruebas usan `SimpleTestCase`, no crean una BD de pruebas ni llaman a proveedores. Los casos de producción se ejecutan en procesos aislados con valores ficticios de prueba; no modifican el `.env` real ni necesitan API keys. Las pruebas de contrato requieren `requirements-dev.txt` y verifican sus ejemplos con jsonschema 4.26.0.

## Contrato JSON v1

El [JSON Schema v1](api/contracts/response-v1.schema.json) fija los nombres, tipos y estados de las respuestas de salud, clima y error. Los endpoints actuales implementan salud, validación y métodos. Los bloques meteorológicos y los errores de proveedores se usarán al integrar las tareas siguientes.

| Método y ruta | Comportamiento actual |
| --- | --- |
| `GET /api/v1/health/` | HTTP 200 con `{"estado":"ok"}` y `Cache-Control: no-store`. No consulta proveedores ni BD. |
| `GET /api/v1/clima/?ciudad=Cordoba&pais=AR` | Valida ciudad, país y región. HTTP 400 si son inválidos; HTTP 503 si son válidos mientras no exista la integración. |

Las rutas se consumen con la barra final. El health es una prueba de vida de Django, no de disponibilidad de OpenWeather/Groq ni de validez de sus credenciales.

### Parámetros de clima

| Parámetro | Reglas |
| --- | --- |
| `ciudad` | Obligatoria, entre 1 y 100 caracteres después de normalizar espacios y Unicode NFC. Admite acentos y nombres compuestos. |
| `pais` | Opcional. Código de dos letras ASCII, por ejemplo AR, ES o ST. Se convierte a mayúsculas; se valida su formato, no su pertenencia al catálogo de países. Un nombre como Argentina es inválido. |
| `region` | Opcional, hasta 100 caracteres después de normalizar. Permite precisar coincidencias dentro de un país. |

Se recortan espacios exteriores y se colapsan los interiores, incluidos tabulaciones y saltos de línea. Se rechazan caracteres de control o invisibles restantes. País/región vacíos se tratan como no especificados. No se modifica la entrada original de la solicitud.

Cada parámetro se envía una sola vez. Los nombres desconocidos y los parámetros duplicados producen 400 en lugar de elegir silenciosamente un valor. Los valores deben codificarse por separado, por ejemplo con `HttpParams` o `URLSearchParams`; acentos, `&`, `+`, `#` y otros caracteres reservados se conservan como datos al decodificar.

Ejemplo codificado: `/api/v1/clima/?ciudad=C%C3%B3rdoba&pais=ar&region=C%C3%B3rdoba`. La consulta interna normalizada será ciudad Córdoba, país AR y región Córdoba.

### Esquema de clima

| Bloque de éxito | Campos del contrato |
| --- | --- |
| `ubicacion` | `nombre`, `pais`, `region`, `latitud`, `longitud`, `desplazamiento_horario_segundos`. |
| `actual` | `fecha_utc`, `temperatura_c`, `sensacion_c`, `humedad_pct`, `viento_kmh`, `descripcion`. |
| `pronostico` | `estado` y lista de `intervalos` con `fecha_utc`, `temperatura_c`, `descripcion`. |
| `recomendacion` | `estado` y `texto`, con `null` cuando no esté disponible. |
| `meta` | `fuente_meteorologica`, `consultado_en_utc` y unidades explícitas. |

Las fechas serán ISO 8601 UTC con sufijo `Z`. Angular presentará la hora de la ciudad usando `desplazamiento_horario_segundos`. Las unidades serán °C, km/h y %. Los cinco bloques de clima son obligatorios y no se admiten campos extra en el esquema v1.

La temperatura y la fecha del clima actual son obligatorias. Sensación térmica, humedad, viento y descripción podrán ser `null` si faltan; humedad se expresa entre 0 y 100 y viento como número no negativo. Cero y temperaturas negativas siguen siendo datos válidos. La región resuelta podrá ser `null` si no existe.

Un pronóstico `disponible` tendrá al menos un intervalo. Si está `no_disponible`, tendrá `intervalos: []`. Una recomendación `disponible` tendrá texto no vacío; si está `no_disponible`, tendrá `texto: null`. Los intervalos no se presentan como promedios diarios. Su orden y la correspondencia con la ubicación se comprobarán al integrar los proveedores.

### Errores y métodos

| HTTP | Código | Situación |
| --- | --- | --- |
| 400 | `ENTRADA_INVALIDA` | Parámetros inválidos; sin llamadas externas. |
| 404 | `CIUDAD_NO_ENCONTRADA` | Sin coincidencias geográficas. |
| 409 | `CIUDAD_AMBIGUA` | Candidatos y posibilidad de precisar país o región. |
| 405 | `METODO_NO_PERMITIDO` | Método no admitido. |
| 429 | `LIMITE_ALCANZADO` | Límite que impide obtener el clima. |
| 503 | `SERVICIO_NO_DISPONIBLE` | Geocodificación o clima temporalmente no disponibles. |

Los errores tendrán `codigo` y `mensaje`. El 400 incluirá `errores` con listas de mensajes por `ciudad`, `pais`, `region` o `consulta`. El futuro 409 incluirá al menos dos `candidatos`, cada uno con nombre, país, región nullable, latitud y longitud. No se reflejan valores privados ni cuerpos internos de proveedores.

POST, PUT, PATCH, DELETE, TRACE, HEAD y OPTIONS directo no están admitidos y devuelven 405 con `Allow: GET`. El cuerpo es JSON, excepto HEAD, que no lleva cuerpo según su semántica HTTP. Un preflight CORS OPTIONS autorizado lo resuelve el middleware con 200 antes de la vista; no es una consulta meteorológica.

```json
{
  "codigo": "ENTRADA_INVALIDA",
  "mensaje": "Revisá los parámetros de la consulta.",
  "errores": {
    "ciudad": ["La ciudad es obligatoria y no puede contener solo espacios."]
  }
}
```

Con clima actual válido y falla de Groq se propone HTTP 200 con `recomendacion.estado = no_disponible` y `texto = null`. Si falla solo el pronóstico, se mantendrá el clima y se informará ese bloque como no disponible. Si no hay clima actual válido, no se pedirá a Groq un consejo meteorológico.

### Ejemplos para preparar Angular

- [Salud](api/contracts/examples/health.json)
- [Éxito de clima](api/contracts/examples/success.json)
- [Clima con recomendación no disponible](api/contracts/examples/partial.json)
- [Entrada inválida](api/contracts/examples/invalid.json)
- [Ciudad ambigua](api/contracts/examples/ambiguous.json)

Todos los ejemplos de clima, fechas, coordenadas y mensajes son fixtures ficticios para probar la estructura JSON. No son observaciones meteorológicas ni resultados reales de OpenWeather/Groq. El endpoint de TK03 no devuelve los ejemplos de éxito como si fueran datos reales.

Para probar la salud local desde PowerShell:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/health/'
```

Consultar clima sin `ciudad` permite comprobar el 400. Consultar `http://127.0.0.1:8000/api/v1/clima/?ciudad=Cordoba&pais=AR` permite comprobar el 503 transitorio de esta etapa. Las validaciones usan [formularios de Django](https://docs.djangoproject.com/en/5.2/ref/forms/validation/) y las vistas devuelven [JsonResponse](https://docs.djangoproject.com/en/5.2/ref/request-response/#jsonresponse-objects).

## Coordinación con el frontend

| Etapa | Dependencia y entrega |
| --- | --- |
| Frontend TK01–TK04 | Preparación y demo con datos ficticios; no acreditan integración real. |
| Backend TK03 | Acordar contrato y respuestas de ejemplo para preparar tipos y adaptación en frontend TK05. |
| Backend TK07–TK08 | API local integrada y verificada para conectar realmente frontend TK05. |
| Backend TK10 | Publicar en Render y comprobar el consumo desde Angular local. |
| Frontend TK10 | Publicar en Vercel, añadir el origen CORS exacto y verificar la integración pública. |

Frontend TK05 permanece pendiente mientras avanzamos con el backend. Su modelo de demo no se debe asumir como contrato de Django. La región opcional del contrato del backend deberá coordinarse con Angular para resolver ambigüedades que persistan al indicar país.

Al iniciar frontend TK05 se adaptará el formulario para enviar códigos de país de dos letras; la demo de frontend TK04 aún admite nombres como Argentina. Esa diferencia está identificada y no se modificó Angular en backend TK03. Las opciones de país y región usarán el esquema de candidatos acordado aquí.

## Planificación del backend

Milestone propuesto: **Backend — Primer incremento**. Tendrá exactamente las diez tareas siguientes. Estados del Kanban: **Pendiente**, **En curso** y **Terminado**. Las fechas no están definidas; P1–P10 expresa secuencia, no días ni duraciones. Responsable propuesto en los archivos: Nahuel Argandoña.

| ID | Tarea | Dependencias del backend | Tamaño | Pruebas | Estado de referencia local |
| --- | --- | --- | --- | --- | --- |
| TK01 | Definir documentación y organización del backend | Ninguna | S | CP15 | En curso: documentación local lista, tablero a cargo del usuario. |
| TK02 | Configurar Django sin base de datos | TK01 | S | CP01, CP12, CP13 | Implementación local verificada; evidencia al final del README. |
| TK03 | Definir contrato JSON y validar las entradas | TK02 | S | CP02, CP03, CP11 | Implementación local verificada; evidencia al final del README. |
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
- Integrar el contrato v1 de TK03 con la resolución de ciudades en TK04 y la composición de respuesta en TK07; adaptar el formulario y tipos al iniciar frontend TK05.
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

## Evidencia local de TK03

24 de octubre de 2026. Windows, Python 3.14.3, Django 5.2.18 y dependencias de prueba de `requirements-dev.txt`. Esta sección refleja el estado posterior a TK02.

- CP02: entrada ausente, vacía, con espacios, demasiado larga, país de formato incorrecto, caracteres invisibles, parámetros repetidos o desconocidos devuelven 400 con errores por campo. Se verificaron acentos, codificación de caracteres reservados, normalización y país/región opcionales.
- CP03: health devuelve 200 sin API keys, red ni BD; métodos no admitidos devuelven 405 y `Allow: GET`. Se conserva el preflight CORS autorizado con 200.
- CP11, alcance de TK03: esquema válido, cinco ejemplos conformes, valores cero/negativos y ausencias permitidas. Se rechazan unidades incorrectas, fechas no UTC o inválidas y estados parciales contradictorios. Los payloads de clima son ejemplos de contrato, no respuestas reales integradas; esa parte de CP11 continúa en TK07–TK08.
- 36 pruebas aprobadas sin base de datos de pruebas. En los tests HTTP de TK03 se bloquearon conexiones de red y BD para detectar cualquier acceso accidental.
- `manage.py check` y `pip check` sin incidencias. HTTP real comprobado en localhost: health 200, entradas inválidas 400, consulta válida 503 y POST 405, todos con JSON y CORS para Angular local.

No se consultó OpenWeather/Groq, no se creó SQLite, no se ejecutaron migraciones ni se modificó el frontend. No se generó commit, PR ni despliegue.
