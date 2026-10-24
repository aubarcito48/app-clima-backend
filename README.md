# App Clima Backend

Backend en Python y Django, en preparación para resolver una ciudad, obtener clima y pronóstico de OpenWeather y generar una recomendación en español con Groq. El frontend Angular consumirá una única API JSON del backend.

Repositorio: [aubarcito48/app-clima-backend](https://github.com/aubarcito48/app-clima-backend). Frontend: [aubarcito48/app-clima](https://github.com/aubarcito48/app-clima).

## Estado actual

**TK07: endpoint de clima inteligente integrado.** La API compone ubicación, clima actual, pronóstico, recomendación y metadatos según el contrato v1. Django opera sin base de datos y el usuario administra el tablero Kanban.

`GET /api/v1/health/` responde 200 con `{"estado":"ok"}` sin proveedores. `GET /api/v1/clima/` valida, resuelve la ubicación y consulta los servicios. Con clima actual válido responde 200, incluso si el pronóstico o la IA no están disponibles. Devuelve 400 para entrada inválida, 404 sin coincidencias, 409 con candidatos ante ambigüedad y 429/503 cuando no puede obtener ubicación o clima actual. La verificación local usa proveedores simulados; no acredita acceso a cuentas reales.

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
scripts/create_local_env.py      Preparación segura del .env local
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
| `OPENWEATHER_API_KEY` | Necesaria para geocodificación y servicios meteorológicos reales. No hace falta para iniciar Django, health o las pruebas. Nunca se envía a Angular. |
| `OPENWEATHER_CONNECT_TIMEOUT_SECONDS` | Timeout de conexión: 3 segundos por defecto. Configurable, mayor que 0 y hasta 30 segundos. |
| `OPENWEATHER_READ_TIMEOUT_SECONDS` | Timeout de operaciones de socket después de conectar: 5 segundos por defecto. Configurable, mayor que 0 y hasta 30 segundos. |
| `GROQ_API_KEY` | Clave privada para el servicio de recomendaciones. Sin clave se devuelve recomendación no disponible, sin intentar red. |
| `GROQ_MODEL` | Identificador del modelo de chat habilitado en la cuenta. Sin modelo se devuelve recomendación no disponible. No se eligió un modelo por defecto. |
| `GROQ_CONNECT_TIMEOUT_SECONDS` | Conexión, escritura y espera del pool: 3 segundos por operación por defecto, mayor que 0 y hasta 30. |
| `GROQ_READ_TIMEOUT_SECONDS` | Lectura del SDK: 8 segundos por operación por defecto, mayor que 0 y hasta 30. |
| `GROQ_MAX_COMPLETION_TOKENS` | Límite de salida del SDK: 160 por defecto, configurable entre 32 y 512. |

El middleware CORS se aplica a `/api/`, admite GET/OPTIONS y no habilita credenciales de navegador ni comodines. Un origen ajeno no recibe `Access-Control-Allow-Origin`. Esto habilita lectura en el navegador; no autentica la API ni bloquea clientes que no usan CORS. [Configuración de django-cors-headers](https://github.com/adamchainz/django-cors-headers#setup).

Para comprobar el entorno de producción se deben preparar sus variables y ejecutar `python manage.py check --settings=config.settings.production`. El `.env` local creado usa `DJANGO_DEBUG=true`, por lo que se debe reemplazar o sobrescribir esa variable con false antes de esa comprobación. En Render se configurarán un secreto propio y los hosts/orígenes reales. La revisión completa de seguridad y el despliegue pertenecen a TK09–TK10.

## Pruebas locales

```powershell
.venv\Scripts\python.exe manage.py test --verbosity 2
.venv\Scripts\python.exe -m pip check
```

Las pruebas usan `SimpleTestCase`, no crean una BD de pruebas ni llaman a proveedores. Los casos de producción se ejecutan en procesos aislados con valores ficticios de prueba; no modifican el `.env` real ni necesitan API keys. Las pruebas de contrato requieren `requirements-dev.txt` y verifican sus ejemplos con jsonschema 4.26.0.

## Contrato JSON v1

El [JSON Schema v1](api/contracts/response-v1.schema.json) fija los nombres, tipos y estados de las respuestas de salud, clima y error. El endpoint integrado devuelve los cinco bloques de clima o un error público conforme al esquema.

| Método y ruta | Comportamiento actual |
| --- | --- |
| `GET /api/v1/health/` | HTTP 200 con `{"estado":"ok"}` y `Cache-Control: no-store`. No consulta proveedores ni BD. |
| `GET /api/v1/clima/?ciudad=Cordoba&pais=AR` | Devuelve 200 con los cinco bloques si hay clima actual válido, o 400/404/409/429/503 según la causa. Puede requerir `region` para resolver ambigüedad. |

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

Los errores tendrán `codigo` y `mensaje`. El 400 incluirá `errores` con listas de mensajes por `ciudad`, `pais`, `region` o `consulta`. El 409 incluye al menos dos `candidatos`, cada uno con nombre, país, región nullable, latitud y longitud. No se reflejan valores privados ni cuerpos internos de proveedores.

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

Con clima actual válido y falla de Groq se devuelve HTTP 200 con `recomendacion.estado = no_disponible` y `texto = null`. Si falla el pronóstico, se mantiene el clima y ese bloque lleva `estado = no_disponible` e `intervalos = []`. Pueden fallar ambos bloques y conservarse el HTTP 200. Si no hay clima actual válido, no se consulta a Groq.

### Ejemplos para preparar Angular

- [Salud](api/contracts/examples/health.json)
- [Éxito de clima](api/contracts/examples/success.json)
- [Clima con recomendación no disponible](api/contracts/examples/partial.json)
- [Entrada inválida](api/contracts/examples/invalid.json)
- [Ciudad ambigua](api/contracts/examples/ambiguous.json)
- [Pronóstico no disponible](api/contracts/examples/forecast-unavailable.json)
- [Pronóstico y recomendación no disponibles](api/contracts/examples/both-unavailable.json)
- [Ciudad no encontrada](api/contracts/examples/not-found.json)
- [Clima no disponible](api/contracts/examples/weather-unavailable.json)
- [Límite del proveedor](api/contracts/examples/rate-limited.json)
- [Método no permitido](api/contracts/examples/method-not-allowed.json)

Todos los ejemplos de clima, fechas, coordenadas y mensajes son fixtures ficticios para probar la estructura JSON. No son observaciones meteorológicas ni resultados reales de OpenWeather/Groq. El endpoint de TK03 no devuelve los ejemplos de éxito como si fueran datos reales.

Para probar la salud local desde PowerShell:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/health/'
```

Consultar clima sin `ciudad` permite comprobar el 400 sin proveedores. Una consulta válida ejecuta los servicios configurados: requiere `OPENWEATHER_API_KEY` para obtener ubicación y clima reales. Sin esa clave responde 503. Si obtiene clima pero falta clave/modelo de Groq, responde 200 con recomendación no disponible. Las validaciones usan [formularios de Django](https://docs.djangoproject.com/en/5.2/ref/forms/validation/) y las vistas devuelven [JsonResponse](https://docs.djangoproject.com/en/5.2/ref/request-response/#jsonresponse-objects).

## Resolución de ciudades de TK04

El cliente usa exclusivamente HTTPS con host fijo `api.openweathermap.org` y ruta `/geo/1.0/direct`. Envía `q`, `limit=5` y `appid` mediante codificación independiente de parámetros. El usuario nunca define el destino de red. No se siguen redirecciones ni se hacen reintentos automáticos.

La [documentación de geocodificación de OpenWeather](https://openweathermap.org/api/geocoding-api) establece un máximo de cinco resultados y limita el código de estado de `q` a EE. UU. Por eso se envía ciudad y país, y `region` se compara localmente con el campo `state` recibido, sin colocar una región libre en la posición del código estadounidense.

La región se puede copiar de un candidato devuelto por la API. Se ignoran diferencias de mayúsculas, acentos y espacios; no se expanden abreviaturas de estados o provincias. Si el proveedor no informa región, esta queda en `null` y no satisface un filtro de región explícito.

Cada resultado se valida antes de filtrar: nombre, país, región opcional y coordenadas numéricas finitas dentro de sus rangos. Se prefiere el nombre en español cuando está disponible. Una fila dañada causa 503 en vez de descartarse para aparentar una coincidencia única. Las filas con el mismo país y coordenadas exactas se consideran duplicados de la misma ubicación.

| Resultado de geocodificación | Comportamiento |
| --- | --- |
| Una coincidencia válida y no truncada | Devuelve internamente `GeoLocation` con nombre, país, región y coordenadas para TK05–TK07. No inventa desplazamiento horario, clima ni consejo. |
| Sin coincidencias, sin alcanzar el límite del proveedor | HTTP 404, `CIUDAD_NO_ENCONTRADA`. Permite corregir ciudad, país o región. |
| Más de una ubicación después de filtrar y deduplicar | HTTP 409, `CIUDAD_AMBIGUA`, con candidatos. No selecciona el primero. |
| Cinco resultados originales y cero/uno después de filtrar | HTTP 503 y pedido de mayor precisión: la lista pudo ser truncada y no se puede asegurar ausencia o unicidad. |
| Clave ausente | HTTP 503 sin abrir conexión. Health y las pruebas siguen funcionando. |
| Límite HTTP 429 del proveedor | HTTP 429 con `LIMITE_ALCANZADO`. |
| Timeout, red, HTTP 401/403 u otra falla externa | HTTP 503 con un mensaje público; no pide iniciar sesión a la persona que usa Angular. |
| JSON incorrecto, respuesta demasiado grande o datos inválidos | HTTP 503 sin reenviar el cuerpo del proveedor. |

El cuerpo externo se limita a 256 KiB y cinco resultados. Los timeouts de conexión y socket se configuran por separado; son límites por operación, no una garantía de tiempo total frente a DNS o respuestas que llegan lentamente. La revisión del presupuesto total de solicitud queda para TK09. No hay reintentos en TK04.

Para usar geocodificación real, colocar la clave únicamente en `OPENWEATHER_API_KEY` del `.env` del backend y reiniciar Django. No ponerla en la URL pública de esta API ni en Angular. Los timeouts nuevos tienen valores por defecto aunque el `.env` existente no los incluya; el archivo privado no se sobrescribe.

La comprobación de TK04 usó mocks y un servidor HTTP local con proveedor simulado. No requirió API keys reales ni consumió consultas externas. TK07 integra actualmente las respuestas meteorológicas completas.

## Clima actual y pronóstico de TK05

`fetch_weather(ubicacion)` recibe un `GeoLocation` de TK04 y devuelve un `WeatherSnapshot` con `ubicacion`, `actual` y `pronostico`. Los tres bloques respetan sus definiciones del esquema v1. No incluyen todavía recomendación ni metadatos de la respuesta HTTP completa: esa composición pertenece a TK07.

El cliente consulta por latitud/longitud los endpoints fijos `/data/2.5/weather` y `/data/2.5/forecast`, con `units=metric` y `lang=es`. Se preparó para los productos [clima actual](https://openweathermap.org/api/current) y [pronóstico de cinco días](https://openweathermap.org/api/forecast5). La disponibilidad real en la cuenta se comprobará con sus credenciales al validar la integración; no se presupone un plan concreto.

Geocodificación y meteorología comparten el transporte HTTPS de `openweather.py`: host/rutas permitidos, parámetros codificados, timeouts de conexión/socket, cuerpo máximo de 256 KiB, sin redirecciones ni reintentos automáticos. La clave permanece exclusivamente en el servidor y no se copian errores externos a las respuestas públicas.

### Normalización

| Dato | Tratamiento |
| --- | --- |
| Temperatura y sensación | Se conservan en °C por la solicitud métrica, incluidos ceros y negativos; no se convierten otra vez desde Kelvin. |
| Viento | La velocidad métrica del proveedor, en m/s, se multiplica por 3,6 y se redondea a tres decimales para km/h. Cero no se confunde con ausencia. |
| Humedad | Se conserva en %, entre 0 y 100. |
| Fechas | Se usan los timestamps Unix `dt`, convertidos a ISO 8601 UTC con sufijo Z. No se usa `dt_txt` ni se suma el desplazamiento de la ciudad a la fecha UTC. |
| Ubicación y hora local | Se conserva la ubicación geocodificada y se añade el desplazamiento en segundos que devuelve el clima actual. No se infiere una zona IANA ni un offset faltante como cero. |
| Campos opcionales ausentes | Sensación, humedad, viento o descripción quedan en `null`, sin inventar valores. |

Fecha, temperatura y desplazamiento horario del clima actual son necesarios para cumplir el contrato; si faltan o son inválidos, el clima actual no se considera disponible. Se rechazan booleanos usados como números, strings numéricos, NaN/Infinity, humedad fuera de rango, viento negativo, fechas inválidas y estructuras incorrectas. Un campo opcional presente pero inválido no se convierte silenciosamente en `null`.

El pronóstico conserva los intervalos provistos y sus temperaturas, ordenados por `dt`. Admite hasta 40 intervalos para el producto de cinco días; no calcula promedios diarios ni rellena huecos. Se comprueba `cnt` cuando está presente. Una lista vacía se presenta como no disponible; intervalos dañados o timestamps duplicados invalidan el bloque en vez de seleccionar o promediar valores contradictorios.

### Fallas parciales

- Si falla el clima actual, se propaga `WeatherFailure` (503) o `WeatherRateLimited` (429), con código y mensaje públicos controlados. No se consulta el pronóstico.
- Si el clima actual es válido y falla el pronóstico, incluso por timeout, 429 o estructura incorrecta, se conserva `actual` y se devuelve `pronostico: {"estado":"no_disponible","intervalos":[]}`.
- Si ambos datos son válidos, el snapshot conserva el clima y todos los intervalos ordenados. Los payloads originales no se modifican.

El servicio está preparado para el posterior HTTP 200 parcial de TK07; TK05 no cambia todavía la vista pública para devolver snapshots incompletos. Las pruebas no necesitan clave real y no hacen llamadas externas. No se modificó el `.env` privado ni se agregaron dependencias.

## Recomendaciones de TK06

`generate_recommendation(snapshot)` recibe el `WeatherSnapshot` normalizado de TK05 y devuelve únicamente el bloque `recomendacion` del contrato v1:

```json
{"estado":"disponible","texto":"Consejo breve en español basado en el clima recibido."}
```

Si falta configuración, el clima actual no es válido, falla el proveedor o el texto no cumple los límites:

```json
{"estado":"no_disponible","texto":null}
```

Los ejemplos de texto anteriores son ilustrativos. El servicio no crea consejos ficticios como reemplazo de una falla. Tampoco modifica ni elimina el snapshot recibido: la composición de TK07 conservará el clima aunque la IA no esté disponible.

### Contexto e instrucciones

Se envía una lista explícita de datos: nombre, país, región y offset de la ubicación; clima actual; unidades; y hasta los primeros ocho intervalos de pronóstico ordenados por TK05. Se informa cuántos intervalos se incluyeron y cuántos existían, sin completar el resto. Coordenadas, campos desconocidos, credenciales y metadatos privados no se incorporan al prompt.

Las instrucciones son un mensaje de sistema fijo. La ubicación y las descripciones se serializan como JSON en otro mensaje con rol usuario, nunca se concatenan dentro de las instrucciones. Se pide un consejo en español, de hasta tres frases y 80 palabras, usando solo los datos entregados, respetando los `null` y sin inventar pronósticos. Si no hay pronóstico, el consejo debe limitarse al clima actual.

El contexto se limita a 12.000 caracteres. Se requiere clima actual válido y no se llama a Groq para completar mediciones faltantes. La separación de mensajes reduce el riesgo de instrucciones dentro de los datos; no garantiza por sí sola la exactitud ni el cumplimiento de un modelo real. Las pruebas verifican estructura y contexto, no la calidad semántica de una respuesta real.

### SDK, tiempos y salida

Se usa el [SDK oficial de Groq para Python](https://github.com/groq/groq-python) con modelo tomado de `.env`, destino fijo `https://api.groq.com`, TLS verificado y sin proxies/base URL del entorno ni redirecciones. Se solicitan una única respuesta, sin streaming y sin uso de herramientas.

Los reintentos del SDK se fijan explícitamente en cero. Los timeouts de conexión, lectura, escritura y pool se establecen con HTTPX; son límites por operación, no un plazo total absoluto. El presupuesto global de solicitud se revisará en TK09. La clave se utiliza solo en la cabecera de autorización del servidor y no forma parte del contexto ni de la respuesta pública.

La respuesta debe contener una única elección completa con `finish_reason=stop`, texto no vacío, hasta 600 caracteres y 80 palabras. Se rechazan truncamientos, respuestas de herramientas, estructuras incorrectas y caracteres de control/invisibles. El texto se devuelve como string JSON, sin ejecutarlo ni interpretarlo como HTML. El frontend deberá seguir renderizándolo como texto.

Timeouts, errores de red, HTTP 401/403/429/5xx, respuestas vacías o inválidas producen el mismo bloque `no_disponible`. No se exponen excepciones, cuerpos del proveedor ni prompts. Los loggers verbosos de Groq/HTTPX/HTTPCore no propagan sus registros; se conservan los logs de Django. Los clientes HTTP se cierran tanto en éxito como en error.

### Configuración real pendiente

Para usar el servicio con una cuenta real, completar `GROQ_API_KEY` y `GROQ_MODEL` en el `.env` privado del backend con un modelo de chat habilitado que admita los parámetros enviados. No colocar esas variables en Angular. La [guía de inicio de Groq](https://console.groq.com/docs/quickstart) explica la configuración de la cuenta.

No se seleccionó un modelo ni se modificó tu `.env` real. La verificación usa el SDK instalado con `httpx.MockTransport`: ninguna llamada sale a Groq ni consume saldo. TK07 integra este servicio en el endpoint público.

## Integración del endpoint de TK07

`query_climate()` encadena validación, resolución de ubicación, clima actual, pronóstico y recomendación. La validación HTTP ocurre antes de llamar a los servicios. Si falla la ubicación no se consulta clima; si falla el clima actual no se consulta pronóstico ni Groq. Cada consulta mantiene sus propios datos, sin historial ni persistencia.

| Resultado | HTTP y contenido |
| --- | --- |
| Clima, pronóstico e IA válidos | 200 con los cinco bloques; ambos estados `disponible`. |
| Falla del pronóstico | 200, pronóstico `no_disponible` con lista vacía. Groq puede responder usando solo el clima actual. |
| Falla o configuración ausente de Groq | 200, recomendación `no_disponible` con texto null. |
| Fallan pronóstico y Groq | 200 con ambos bloques no disponibles y el clima actual conservado. |
| Ubicación ausente o ambigua | 404 o 409; el segundo incluye candidatos para precisar la consulta. |
| Límite que impide resolver ubicación o clima actual | 429 con error público. |
| Ubicación o clima actual no disponibles | 503 con error público, sin fabricar mediciones. |

`meta.consultado_en_utc` registra el inicio de la consulta; `actual.fecha_utc` conserva la fecha de la medición del proveedor. Las coordenadas resueltas se usan para clima y pronóstico de la misma consulta. Las respuestas exitosas llevan `Cache-Control: no-store`. No se devuelven claves, prompts ni cuerpos privados de error.

Para frontend TK05, consumir `/api/v1/clima/` con `ciudad`, código `pais` de dos letras y `region` opcional. Adaptar los tipos a los cinco bloques del contrato y representar por separado los estados de pronóstico e IA. Ante 409, usar los candidatos para precisar país/región; ante 400, mostrar los errores de entrada. Los ejemplos versionados permiten preparar esas vistas sin consultar proveedores. CORS local admite los orígenes Angular de localhost y 127.0.0.1 en el puerto 4200. El frontend permanece sin cambios en esta tarea.

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
| TK04 | Resolver ciudades con OpenWeather | TK03 | M | CP04, CP05 | Implementación local verificada con proveedor simulado; evidencia al final. |
| TK05 | Consultar y normalizar clima actual y pronóstico | TK04 | M | CP06, CP07, CP10 | Servicios verificados con proveedor simulado; evidencia al final. |
| TK06 | Generar recomendaciones con Groq | TK05 | M | CP08, CP09 | Servicio verificado con SDK y transporte simulado; evidencia al final. |
| TK07 | Integrar el endpoint de clima inteligente | TK03, TK05, TK06 | M | CP09, CP10, CP11 | Implementación local verificada con proveedores simulados; evidencia al final. |
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
- Ampliar la revisión integral en backend TK08; adaptar el formulario y tipos al iniciar frontend TK05 usando el endpoint integrado de TK07.
- Verificar en la cuenta la disponibilidad de los productos de clima actual y pronóstico de cinco días preparados en TK05 antes de validar con datos reales.
- Seleccionar en la cuenta un modelo de Groq habilitado y validar sus permisos y compatibilidad con la petición. TK06 ya fija límites de salida, timeouts por operación y cero reintentos; el presupuesto global se revisará en TK09.
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

## Evidencia local de TK04

24 de octubre de 2026. Windows, Python 3.14.3, Django 5.2.18. Sin dependencias nuevas: el transporte usa la biblioteca estándar de Python.

- CP04: cliente HTTPS con host/ruta fijos, parámetros codificados y timeouts explícitos; ubicación válida con nombre español, país, región y coordenadas, incluidos ceros. Sin llamadas externas en las pruebas.
- CP05: listas vacías producen 404, varias ubicaciones producen 409 con candidatos conformes al esquema, país/región permiten precisar y no se elige silenciosamente la primera coincidencia. Se verificaron duplicados y el límite de cinco resultados.
- Fallas controladas: timeout en conexión/envío/lectura, error de protocolo, HTTP 401/403/429/5xx, redirecciones, JSON inválido, respuestas grandes, números no finitos, coordenadas fuera de rango y filas dañadas. Los cuerpos del proveedor y la clave no se copian a mensajes públicos.
- 63 pruebas aprobadas sin BD ni red externa. Se conserva la regresión de contrato, CORS, health y validación previa a proveedores. `manage.py check` y `pip check` sin incidencias.
- HTTP local con geocodificación simulada: 400, 404, 409, 429 y 503 verificados con JSON y CORS para Angular. La consulta resuelta devuelve todavía 503 porque no se implementó el clima de TK05.

No se probó una cuenta real de OpenWeather, no se consumieron consultas externas ni se consultó Groq. El `.env` privado y el frontend se conservaron sin cambios. No se creó BD, migración, endpoint adicional, commit, PR ni despliegue.

## Evidencia local de TK05

24 de octubre de 2026. Windows, Python 3.14.3, Django 5.2.18. Sin dependencias nuevas.

- CP06: temperaturas cero/negativas, sensación negativa, humedad cero/ausente y viento cero o convertido desde m/s. Por ejemplo, 2,5 m/s se normaliza a 9 km/h. Los datos opcionales ausentes quedan en null y los valores inválidos producen error controlado.
- CP07: timestamps Unix a UTC, cambio de día, offset local recibido y pronóstico ordenado sin modificar el original, inventar promedios ni usar `dt_txt`. Se comprobaron listas vacías, duplicados, `cnt` incorrecto, filas inválidas y bloques conformes al esquema v1.
- CP10, capa de servicios: falla del clima actual detiene la consulta de pronóstico; falla o límite del pronóstico conserva clima válido y marca ese bloque como no disponible. La respuesta HTTP completa y sus fallas parciales se integrarán en TK07 y se verificarán integralmente en TK08.
- 94 pruebas aprobadas, incluida la regresión de geocodificación después de compartir el transporte HTTPS. Red y conexiones de BD bloqueadas en las pruebas nuevas.
- `manage.py check` y `pip check` sin incidencias. Se verificaron endpoints fijos, coordenadas de la ubicación resuelta, unidades métricas, idioma español, límites de respuesta y errores saneados.

No se usó una cuenta real de OpenWeather, no se hicieron consultas externas ni se integró Groq. El frontend y el `.env` privado se conservaron sin cambios. No se creó BD, migración, endpoint adicional, commit, PR ni despliegue.

## Evidencia local de TK06

24 de octubre de 2026. Windows, Python 3.14.3, Django 5.2.18, groq 1.7.0 y HTTPX 0.28.1. Dependencias y versiones transitivas fijadas en `requirements.txt`.

- CP08: se capturó la petición real del SDK en transporte simulado. Modelo configurable, roles separados, contexto con mediciones y unidades, ceros y nulls conservados, pronóstico acotado sin promedios y campos privados excluidos.
- CP09, servicio: timeout, conexión fallida, 401/403/429/5xx, redirecciones, texto vacío, truncado, excesivo o respuesta de herramientas devuelven `no_disponible`/null. Se comprobó una sola petición, sin reintentos, cierre de conexiones y snapshot meteorológico intacto.
- Comprobada la conformidad del bloque con el JSON Schema v1. Se verificó también el consejo basado solo en clima actual cuando falta pronóstico, y que no haya petición sin clave/modelo o sin clima actual válido.
- 116 pruebas aprobadas, sin red externa ni base de datos. Verificada la no propagación de clave y prompt en logs incluso habilitando niveles verbosos de los loggers del proveedor durante la prueba.
- `manage.py check` y `pip check` sin incidencias. No se probaron permisos, cuotas ni calidad de un modelo real; esa validación queda para la integración con las cuentas reales.

El `.env` privado y el frontend se conservaron sin cambios. No se realizaron consultas externas ni se creó BD, migración, endpoint nuevo, commit, PR o despliegue. TK07 compondrá los servicios de ubicación, clima y recomendación en la respuesta HTTP completa.

## Evidencia local de TK07

24 de octubre de 2026. Windows, Python 3.14.3, Django 5.2.18, groq 1.7.0 y HTTPX 0.28.1.

- CP09: el endpoint conserva HTTP 200 y las mediciones ante límite, error, timeout, texto vacío o truncado de Groq. Sin clave/modelo no intenta consultar la IA.
- CP10: una falla del pronóstico permite responder con clima actual y consejo; la falla de ambos bloques conserva el clima. Una falla del clima actual devuelve 429/503 y detiene pronóstico y Groq.
- CP11: integración conforme al esquema v1 con los cinco bloques, coordenadas consistentes, fechas UTC, unidades, valores cero/negativos y ausencias null. Consultas sucesivas conservan sus propios datos. Entrada inválida, health y métodos no admitidos no llaman a proveedores.
- 129 pruebas aprobadas sin BD ni red externa. Los once ejemplos versionados cubren éxito, respuestas parciales, salud y errores.
- Recorrido por HTTP mediante WSGI local y transportes simulados: éxito y las tres combinaciones parciales devuelven 200; falta de clima actual devuelve 503 y ambigüedad 409. Comprobados JSON Schema, CORS para Angular y `Cache-Control: no-store` en respuestas exitosas.
- `manage.py check`, `pip check` y `git diff --check` sin incidencias.

No se verificaron cuentas, cuotas, permisos ni calidad de un modelo real. El frontend y el `.env` privado se conservaron sin cambios. No se creó BD, migración, commit, PR ni despliegue. Backend TK08 queda pendiente para la revisión integral prevista.
