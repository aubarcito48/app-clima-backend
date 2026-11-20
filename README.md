# StitchWeather · Backend

API de la aplicación meteorológica StitchWeather. Consulta el clima y el
pronóstico, prepara recomendaciones con IA y genera la voz de Isa en español
e inglés. Las claves de OpenWeather y Groq permanecen en este servidor.

**[Probar la aplicación](https://app-clima-ecru.vercel.app/)** ·
[Frontend y captura de pantalla](https://github.com/aubarcito48/app-clima)

## Tecnologías

| Tecnología | Función |
| --- | --- |
| Python y Django 5.2 | API HTTP, validación y configuración del servidor. |
| OpenWeather | Datos meteorológicos y capas del mapa. |
| Groq | Recomendaciones y dirección de la actuación de Isa. |
| Piper y ONNX Runtime | Síntesis local de voz: Sharvard en español y Cori en inglés. |
| Motor propio de sincronización | Metadatos para acompañar la voz con los movimientos de boca. |
| SQLite de solo lectura | Catálogo geográfico incluido en `data/places.sqlite`. |

**No hay cuentas de usuario ni base de datos Django que migrar.** El catálogo
geográfico es un archivo estático que ya está versionado; no necesitás PostgreSQL
ni ejecutar `migrate`, crear un administrador o reconstruir ese catálogo para iniciar.

## Requisitos

- Git y Python **3.14**, la versión indicada por `.python-version` es 3.14.3.
- `pip` y `venv`.
- Claves propias de OpenWeather y Groq.
- Internet para instalar dependencias, descargar las voces y consultar proveedores.
- Espacio para el entorno de Python, dos voces originales y sus copias preparadas
  para alineación. Los modelos no se incluyen en Git.

Los ejemplos siguientes usan Windows y PowerShell. Para la voz se necesitan los
paquetes de `requirements-voice.txt`, además de las dependencias de la API.

## Instalación desde cero

### 1. Descargar y preparar Python

```powershell
git clone https://github.com/aubarcito48/app-clima-backend.git
cd app-clima-backend
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Los comandos usan directamente el Python del entorno: no hace falta activar
`.venv` ni modificar la política de ejecución de PowerShell.

### 2. Crear la configuración privada

```powershell
.\.venv\Scripts\python.exe scripts/create_local_env.py
```

El script crea `.env` desde el ejemplo con un secreto aleatorio. Si el archivo
ya existe, lo conserva. Abrilo en tu editor y completá:

| Variable | Valor que necesitás |
| --- | --- |
| `OPENWEATHER_API_KEY` | Tu clave de OpenWeather para los datos meteorológicos. |
| `GROQ_API_KEY` | Tu clave de Groq para las recomendaciones. |
| `GROQ_MODEL` | Modelo disponible para tu cuenta; el ejemplo proporciona el valor inicial. |
| `CORS_ALLOWED_ORIGINS` | Origen del frontend. El ejemplo permite `http://localhost:4200` y `http://127.0.0.1:4200`. |

Conservá `DJANGO_SECRET_KEY`, los hosts y los valores de desarrollo generados
para la primera ejecución local. No subas `.env` ni claves a GitHub.

### 3. Preparar la voz de Isa

Para instalar también la voz y la sincronización de boca:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-voice.txt
.\.venv\Scripts\python.exe scripts/install_voice.py
```

El instalador descarga las voces española e inglesa, verifica tamaño y SHA256 y
prepara las versiones con alineación en `models/piper-sharvard/`. No hace falta
ejecutar `prepare_isa_alignment.py` por separado en la instalación normal.
Este paso puede tardar y debe terminar antes de probar el audio.

Podés iniciar solo la API meteorológica antes de completar este paso, pero la
voz no estará disponible hasta instalar sus dependencias y modelos.

### 4. Iniciar el servidor

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Dejá esta terminal abierta. La API queda en `http://localhost:8000`; luego abrí
otra terminal para iniciar el [frontend](https://github.com/aubarcito48/app-clima#ejecutar-el-frontend).
El frontend usa la dirección del servidor sin agregar `/api/v1` a su variable de entorno.

## Comprobar la instalación

1. Abrí `http://localhost:8000/api/v1/health/`: debe responder `{"estado":"ok"}`.
   Este control comprueba que Django responde; no verifica las claves ni las voces.
2. Con el frontend iniciado, buscá una ciudad y comprobá clima y pronóstico.
3. Revisá que aparezca una recomendación y después reproducí su voz con Isa.
4. Cambiá a inglés y repetí la consulta para comprobar la segunda voz.

## Rutas de la API

| Ruta | Función |
| --- | --- |
| `/api/v1/health/` | Estado básico del servidor. |
| `/api/v1/lugares/` | Búsqueda geográfica. |
| `/api/v1/clima/` | Consulta meteorológica y recomendación. |
| `/api/v1/alertas/` | Alertas. |
| `/api/v1/mapa/` | Capas meteorológicas. |
| `/api/v1/voz/` | Generación de audio y datos de actuación de Isa. |

El frontend del mismo proyecto implementa los parámetros y cuerpos de estas rutas.
La voz se genera en el backend; no depende de tener una voz del sistema instalada
en el navegador del visitante.

## Problemas frecuentes

| Síntoma | Qué revisar |
| --- | --- |
| Falta `DJANGO_SECRET_KEY` | Ejecutá `scripts/create_local_env.py`; si ya existe `.env`, completá la variable sin publicar su valor. |
| El estado es correcto pero el clima falla | Revisá la clave de OpenWeather, conectividad y límites del proveedor. El estado básico no consulta servicios externos. |
| No se generan recomendaciones | Revisá la clave de Groq y que `GROQ_MODEL` esté disponible para tu cuenta. |
| El texto aparece pero Isa no habla | Verificá la instalación de voz y los modelos. Si el audio se generó, hacé clic sobre Isa y revisá el volumen y permisos del navegador. |
| Error de CORS | Comprobá que el origen exacto del frontend, incluido su puerto, figure en `CORS_ALLOWED_ORIGINS`. Reiniciá Django después de editar `.env`. |
| Puerto 8000 ocupado | Usá `runserver 8001` y actualizá `PUBLIC_API_BASE_URL_DEVELOPMENT` en el frontend. |
| La voz tarda mucho | La síntesis depende de CPU y memoria; la primera solicitud puede preparar el modelo. Los tiempos locales no garantizan los del alojamiento. |

## Producción y organización

`runserver` es para desarrollo. El repositorio separa configuración local y de
producción en `config/settings/`. `requirements-production.txt` incluye API, voz
y Gunicorn para el servidor Linux. Antes de publicar, configurá hosts y orígenes
reales, HTTPS, un secreto privado y `DJANGO_DEBUG=false`; no copies los valores
de desarrollo como configuración pública.

Las vistas están en `api/views/`, la validación en `api/validation/` y los
servicios por funcionalidad en `api/services/`. Los instaladores están en
`scripts/`. Las pruebas de navegador se conservan en el repositorio del frontend.

Para [informar un error](https://github.com/aubarcito48/app-clima-backend/issues),
incluí pasos, sistema operativo, versión de Python y el error sin claves,
cabeceras privadas ni el archivo `.env`.
