# App Clima Backend

API de la app del clima, desarrollada con Python y Django. Resuelve ubicaciones, consulta el clima y pronóstico de OpenWeather, y genera recomendaciones con Groq en español o inglés. No utiliza base de datos.

Frontend: [StitchWeather](https://github.com/aubarcito48/app-clima).

Los consejos de Groq están limitados a 280 caracteres (incluidos espacios) y
40 palabras. El prompt pide hasta dos frases: ropa recomendada y motivo climático,
con una adaptación para más tarde cuando el pronóstico lo justifique. Evita
repetir todas las mediciones, saludos y despedidas. Isa lee el mismo texto completo.
Las respuestas que exceden los límites se consideran no disponibles; no se cortan
frases a mitad ni se hace otra llamada a Groq. Se conserva el presupuesto de tokens
de razonamiento del modelo: la brevedad se controla por instrucciones y validación.
Esto reduce la duración del audio, pero no garantiza resolver por sí solo el pico
de memoria de la primera generación de Kokoro en Render.

## Ejecución local

Versión de Python del proyecto: 3.14.3. Desde esta carpeta, en PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe scripts/create_local_env.py
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

El script crea `.env` con un secreto de Django y conserva el archivo si ya existe. Configurá allí `OPENWEATHER_API_KEY`, `GROQ_API_KEY` y `GROQ_MODEL` para usar los proveedores. Las demás opciones están en [.env.example](.env.example). No se requieren migraciones.

## Voz de Isabel (Isa)

La voz opcional es Dora de Kokoro (`ef_dora`, español), la misma de Aubar.
Se sintetiza localmente y se envía como WAV al navegador, sin reproducir audio en el servidor.
No requiere otra API key. Dora no tiene una variante cordobesa documentada.

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-voice.txt
.venv\Scripts\python.exe scripts/install_voice.py
```

Para reutilizar una carpeta que ya contenga el modelo INT8 y las voces:

```powershell
.venv\Scripts\python.exe scripts/install_voice.py --from-dir ../../botbar/models/kokoro-v1.0
```

El instalador verifica tamaño y SHA256. Los modelos quedan fuera de Git.
Se usa `kokoro-v1.0.int8.onnx` (92.361.271 bytes) de la versión
[model-files-v1.0](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0),
con la misma voz femenina `ef_dora`. El modelo FP32 antiguo no se usa como fallback.
La carpeta original de Aubar puede tener solo FP32: en ese caso ejecutá el
instalador sin `--from-dir` para descargar INT8.
`ISA_MODEL_DIR` permite configurar otra carpeta (usá también `--target` al instalar).
Reiniciá Django después de instalar. En otro servidor hay que instalar las dependencias
y modelos allí; la instalación local no los publica.

`POST /api/v1/voz/`, JSON `{"texto":"consejo exacto de Groq"}`, devuelve `audio/wav`.
Admite hasta 600 caracteres, una síntesis simultánea por proceso y 45 segundos de espera;
devuelve 429 si está ocupado y 503 si falta el motor, los modelos o falla la síntesis.
No guarda texto ni audio y no realiza descargas durante la consulta. El worker carga
el modelo en cada petición para poder terminarlo al superar el tiempo máximo.
Para despliegues públicos, aplicá límites de solicitudes en el proxy como en el resto de la API.
El clima sigue funcionando aunque la voz no esté instalada.

### Memoria y despliegue de la voz

El worker convierte el texto completo a fonemas una sola vez, antes de cargar
el modelo. Después limita cada entrada de inferencia a 32 símbolos de pronunciación,
prefiriendo puntuación y espacios: los números y unidades ya están expandidos.
Une los fragmentos en un solo WAV de 24 kHz, con pausas de 20 ms entre grupos
y 80 ms después de puntuación de cierre. Conserva Dora, español y velocidad 0,95. Libera los arrays
de cada fragmento, usa un hilo de ONNX y desactiva su arena, patrón de memoria
y prepacking de pesos para reducir copias adicionales.
El proceso termina al finalizar cada consulta; los límites de 600 caracteres,
90 segundos de audio y 45 segundos de ejecución siguen vigentes.

Build Command de Render, ejecutado desde la raíz del backend:

```sh
pip install -r requirements.txt && pip install gunicorn && pip install -r requirements-voice.txt && python scripts/install_voice.py
```

Conservar un solo worker de Gunicorn; el bloqueo de síntesis es por proceso.
No requiere cambios en el frontend. Un redeploy ejecuta el instalador y descarga
el nuevo modelo verificado. Los archivos FP32 que puedan quedar en disco no se cargan.

Prueba real opcional (requiere las dependencias y modelos instalados):

```powershell
.venv\Scripts\python.exe scripts/profile_voice.py
```

En Linux/Render: `python scripts/profile_voice.py`. Informa el pico RSS del proceso
de voz y guarda `tmp/isa-int8-sample.wav`; `--text` permite probar otros consejos.
No mide Django, Gunicorn ni la memoria total del contenedor. Con la configuración
de 32 símbolos, la prueba de 397 caracteres en Windows tuvo un pico de 247 MiB y
demoró unos 23 segundos; un consejo de 130 caracteres tuvo 245 MiB y unos 10 segundos.
No garantiza entrar en 512 MB en Linux ni finalizar dentro de 45 segundos en una CPU
más limitada. El despliegue debe validarse con consejos largos y concurrencia.

Las pruebas previas en Render con INT8 y fragmentos de texto (incluso de 48 caracteres)
superaron 512 MB durante el primer fragmento. El contenedor estaba en 305–310 MiB
con el modelo cargado. Contar caracteres no limitaba la expansión de la pronunciación;
la configuración actual controla esa entrada después de convertirla a fonemas.
Queda pendiente validar esta configuración en Render.

En Linux cada petición de voz registra eventos `isa_memory` en stderr heredado,
antes de cargar librerías/modelo y antes/después de cada fragmento. Los campos
`phonemizing`/`phonemes_ready` e `inference_start`/`inference_done` permiten distinguir
preparación de pronunciación y cálculo de ONNX. `tokens` registra solo la cantidad
de unidades que recibe la inferencia, nunca su contenido. Los campos
`rss_mib` y `peak_rss_mib` corresponden al proceso que registra; `cgroup_current_mib`
y `cgroup_limit_mib` al contenedor cuando sus contadores están disponibles.
`cgroup_anon_mib` y `cgroup_file_mib` separan memoria anónima y archivos/caché.
No se registran texto, audio, rutas ni credenciales. Si el proceso es terminado por
OOM, los eventos anteriores permanecen en los logs, en lugar de quedar capturados
en un pipe que se pierde con el reinicio.

## API y pruebas

- `GET /api/v1/health/`: estado del servicio.
- `GET /api/v1/clima/`: clima, pronóstico y recomendación por nombre o coordenadas; admite `idioma=es|en`.
- `GET /api/v1/lugares/`: sugerencias de lugares.
- `GET /api/v1/alertas/`: alertas meteorológicas.

```powershell
.venv\Scripts\python.exe scripts/test_backend.py
```

Las pruebas usan proveedores simulados, sin claves reales, red ni base de datos. El contrato JSON está en [api/contracts](api/contracts/).
