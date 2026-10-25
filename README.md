# App Clima Backend

Backend en Python y Django para resolver una ciudad, obtener clima y pronóstico de OpenWeather y generar una recomendación con Groq. El frontend Angular consume una única API JSON del backend.

`GET /api/v1/clima/` acepta el parámetro opcional `idioma=es` o `idioma=en`, tanto en consultas por nombre como por coordenadas. Por defecto usa español. El idioma se aplica a las descripciones de OpenWeather y al consejo de Groq; no cambia la estructura del contrato ni requiere credenciales o variables nuevas. Los avisos oficiales del SMN conservan su idioma original.

Repositorio: [aubarcito48/app-clima-backend](https://github.com/aubarcito48/app-clima-backend). Frontend: [aubarcito48/app-clima](https://github.com/aubarcito48/app-clima).

## Estado actual

**TK09: seguridad y configuración de producción preparadas.** Se validan hosts y orígenes concretos, se exige HTTPS y se registran eventos mínimos sin mensajes ni trazas internas. La suite aislada aprueba 140 pruebas; el despliegue y su comprobación en Render corresponden a TK10.

`GET /api/v1/health/` responde 200 con `{"estado":"ok"}` sin proveedores. `GET /api/v1/clima/` valida, resuelve la ubicación y consulta los servicios. Con clima actual válido responde 200, incluso si el pronóstico o la IA no están disponibles. Devuelve 400 para entrada inválida, 404 sin coincidencias, 409 con candidatos ante ambigüedad y 429/503 cuando no puede obtener ubicación o clima actual. La verificación local usa proveedores simulados; no acredita acceso a cuentas reales.

La numeración TK01–TK10 de este repositorio es independiente de la del frontend. En las conversaciones y referencias cruzadas se debe indicar siempre a qué repositorio pertenece cada tarea. Los requisitos e historias del backend usan el prefijo BE.

## Datos opcionales para StitchWeather

La respuesta v1 admite `actual.amanecer_utc` y `actual.atardecer_utc` (fechas UTC), `icono` en clima actual e intervalos (código de icono de OpenWeather) y `pronostico.intervalos[].precipitacion_pct` (0–100). Son extensiones opcionales compatibles con respuestas anteriores; se omiten cuando el proveedor no los entrega. Se normalizan de las mismas llamadas de clima actual y pronóstico, sin nuevas credenciales, peticiones ni persistencia. El esquema `api/contracts/response-v1.schema.json` incluye estos campos. Angular aplica el desplazamiento horario de la ciudad para mostrar los horarios solares.

La verificación aislada comprende 153 pruebas y bloquea red y bases de datos. Los casos nuevos cubren horarios solares, iconos, probabilidad cero, conversión de probabilidad a porcentaje y valores inválidos.

## Alcance

- Recibir un nombre de lugar con filtros opcionales, o un par de coordenadas para ubicación actual.
- Resolver ubicación y coordenadas, diferenciando ausencia y ambigüedad.
- Consultar clima actual y los intervalos de pronóstico realmente disponibles.
- Normalizar unidades y fechas, conservando valores ausentes sin inventar datos.
- Pedir a Groq un consejo breve basado en la ubicación y los datos meteorológicos de esa consulta.
- Devolver JSON estable, errores recuperables y disponibilidad parcial por bloque.
- Exponer un health check independiente de los proveedores.

No se incluyen base de datos, ORM, modelos persistentes, migraciones, cuentas, autenticación, sesiones, administrador ni historial funcional de consultas. En producción los registros operativos se envían a consola mediante una lista de campos permitidos.

## Responsabilidades y organización prevista

```text
Angular → Django → OpenWeather
                 → Groq
```

Angular se encarga de la entrada, las consultas HTTP y la presentación. Django valida, resuelve la ubicación, consulta los proveedores, normaliza sus respuestas y protege las claves. El despliegue previsto es Django en Render y Angular en Vercel.

La configuración y las rutas están separadas de la aplicación `api`. Las vistas, validadores, esquemas de respuesta y clientes de OpenWeather/Groq se implementarán en las tareas correspondientes. Los destinos externos serán fijos; ciudad, país y región se enviarán como parámetros codificados.

## Versiones e instalación local

Configuración verificada con Python 3.14.3, Django 5.2.18 LTS, django-cors-headers 4.9.0 y python-dotenv 1.2.4. `requirements.txt` fija también las dependencias transitivas. La [compatibilidad oficial de Django 5.2](https://docs.djangoproject.com/en/5.2/faq/install/) incluye Python 3.14 desde Django 5.2.8.

TK06 añade el SDK oficial groq 1.7.0 y HTTPX 0.28.1, con sus dependencias fijadas. Después de actualizar el repositorio, volver a instalar `requirements-dev.txt` para ejecutar la suite completa.

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
api/views.py                     Health, endpoint integrado y errores públicos
api/validation.py                Formulario y consulta normalizada sin persistencia
api/responses.py                 JSON uniforme y control de método GET
api/operational.py               Logs seguros de consola y eventos HTTP en producción
api/services/openweather.py      Transporte HTTPS común con destinos fijos y límites
api/services/geocoding.py        Resolución de ubicaciones de OpenWeather
api/services/weather.py          Clima actual, pronóstico y normalización sin HTTP público
api/services/recommendations.py  Contexto meteorológico y recomendación breve con Groq
api/services/climate.py          Orquestación por consulta y composición de los cinco bloques
api/contracts/                   JSON Schema v1 y ejemplos ficticios versionados
api/management/commands/         runserver sin comprobación de migraciones
api/tests.py                     Pruebas de configuración sin base de datos
api/test_contract.py             Pruebas de entradas, HTTP y esquema JSON
api/test_geocoding.py            Pruebas de transporte, geocodificación y errores con mocks
api/test_weather.py              Pruebas de unidades, fechas y fallas meteorológicas parciales
api/test_recommendations.py      Pruebas del SDK con transporte HTTP en memoria
api/test_climate.py              Integración del endpoint con proveedores simulados
api/test_regression.py           Recorrido HTTP completo con transportes simulados
api/test_security.py             Seguridad HTTP, logs y configuración de producción
scripts/create_local_env.py      Preparación segura del .env local
scripts/test_backend.py          Suite aislada de credenciales, red y BD
```

`manage.py` usa `config.settings.development` por defecto. WSGI/ASGI usan `config.settings.production` salvo que se establezca explícitamente `DJANGO_SETTINGS_MODULE`. La instalación del servidor de producción y los comandos de Render quedan para TK10.

## Configuración por entorno

`.env` se lee con `python-dotenv`, sin sobrescribir las variables del sistema o de Render. `.env`, sus variantes, `.venv`, cachés y archivos SQLite quedan excluidos de Git; `.env.example` sí se versiona sin secretos.

| Variable | Uso actual |
| --- | --- |
| `DJANGO_SECRET_KEY` | Obligatoria. Secreto privado generado para desarrollo; producción requiere uno robusto y no admite el prefijo inseguro de Django. |
| `DJANGO_DEBUG` | Booleano explícito. Local admite true/false; producción rechaza true. |
| `DJANGO_ALLOWED_HOSTS` | Hosts separados por comas. Local: localhost, 127.0.0.1 y [::1]. Producción exige hosts explícitos sin `*`. |
| `CORS_ALLOWED_ORIGINS` | Orígenes separados por comas. Local: http://localhost:4200 y http://127.0.0.1:4200. |
| `DJANGO_TRUST_PROXY_HTTPS` | false por defecto. Activa confianza en `X-Forwarded-Proto` solo detrás de un proxy que elimine el valor del cliente y establezca el suyo. |
| `OPENWEATHER_API_KEY` | Necesaria para geocodificación y servicios meteorológicos reales. No hace falta para iniciar Django, health o las pruebas. Nunca se envía a Angular. |
| `OPENWEATHER_CONNECT_TIMEOUT_SECONDS` | Timeout de conexión: 3 segundos por defecto. Configurable, mayor que 0 y hasta 30 segundos. |
| `OPENWEATHER_READ_TIMEOUT_SECONDS` | Timeout de operaciones de socket después de conectar: 5 segundos por defecto. Configurable, mayor que 0 y hasta 30 segundos. |
| `GROQ_API_KEY` | Clave privada para el servicio de recomendaciones. Sin clave se devuelve recomendación no disponible, sin intentar red. |
| `GROQ_MODEL` | Identificador del modelo de chat habilitado en la cuenta. Sin modelo se devuelve recomendación no disponible. No se eligió un modelo por defecto. |
| `GROQ_CONNECT_TIMEOUT_SECONDS` | Conexión, escritura y espera del pool: 3 segundos por operación por defecto, mayor que 0 y hasta 30. |
| `GROQ_READ_TIMEOUT_SECONDS` | Lectura del SDK: 8 segundos por operación por defecto, mayor que 0 y hasta 30. |
| `GROQ_MAX_COMPLETION_TOKENS` | Límite de salida del SDK: 160 por defecto, configurable entre 32 y 512. |

El middleware CORS se aplica a `/api/`, admite GET/OPTIONS y no habilita credenciales de navegador ni comodines. Un origen ajeno no recibe `Access-Control-Allow-Origin`. Esto habilita lectura en el navegador; no autentica la API ni bloquea clientes que no usan CORS. [Configuración de django-cors-headers](https://github.com/adamchainz/django-cors-headers#setup).

Para comprobar el entorno de producción se deben preparar sus variables y ejecutar `python manage.py check --deploy --settings=config.settings.production`. El `.env` local creado usa `DJANGO_DEBUG=true`, por lo que se debe sobrescribir esa variable con false para esa comprobación. En Render se configurarán un secreto propio y los hosts/orígenes reales. Las decisiones y advertencias de seguridad de TK09 se explican más abajo; el despliegue pertenece a TK10.

## Pruebas locales

```powershell
.venv\Scripts\python.exe scripts/test_backend.py
.venv\Scripts\python.exe scripts/test_backend.py --shuffle 24082026 --verbosity 2
.venv\Scripts\python.exe -m pip check
```

Las pruebas usan `SimpleTestCase`, no crean una BD de pruebas ni llaman a proveedores. El comando recomendado `scripts/test_backend.py` deshabilita la lectura de dotenv, establece configuración ficticia y claves vacías, y bloquea sockets, SQLite y conexiones de Django antes de inicializar la aplicación. Las pruebas que necesitan proveedores usan claves ficticias y transportes simulados. No hace falta crear `.env` para ejecutar esta suite.

El bloqueo falla ante un intento de conexión no simulado y comprueba al terminar que no se haya utilizado. Los casos de producción se ejecutan en subprocesos con valores ficticios y dotenv deshabilitado; comprueban configuración y, desde TK09, HTTP y logs con el cliente de Django y conexiones bloqueadas. El comando no modifica archivos de entorno ni inicia un servidor. `--shuffle` permite repetir un orden alternativo mediante una semilla explícita.

El comando estándar `manage.py test` sigue disponible, pero carga la configuración local de Django; para una ejecución independiente de las credenciales se recomienda el script anterior. Las pruebas de contrato requieren `requirements-dev.txt` y verifican sus ejemplos con jsonschema 4.26.0.
