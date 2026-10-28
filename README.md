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
La brevedad reduce la duración del audio que genera Piper y el tiempo de espera
antes de que Isa empiece a hablar.

## Ejecución local

Versión de Python del proyecto: 3.14.3. Desde esta carpeta, en PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe scripts/create_local_env.py
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

El script crea `.env` con un secreto de Django y conserva el archivo si ya existe. Configurá allí `OPENWEATHER_API_KEY`, `GROQ_API_KEY` y `GROQ_MODEL` para usar los proveedores. Las demás opciones están en [.env.example](.env.example). No se requieren migraciones.

## Voz de Isa

Se usa **Piper 1.8.0**, modelo `es_ES-sharvard-medium`, hablante femenino
`F = 1`, español de España. El modelo contiene dos hablantes; el worker valida
esa configuración y fija el femenino. No acepta una voz elegida desde el cliente.

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-voice.txt
.venv\Scripts\python.exe scripts/install_voice.py
```

El instalador descarga modelo, configuración y MODEL_CARD desde una revisión fija
de [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices/tree/5041a7a49ae5b3a0f30e6837769eb03fdbb231bd/es/es_ES/sharvard/medium).
Verifica tamaño y SHA256 antes de publicar cada archivo. Quedan fuera de Git en
`models/piper-sharvard`. Para reutilizar otra descarga de estos mismos archivos:
`python scripts/install_voice.py --from-dir RUTA`.

`ISA_MODEL_DIR` permite usar otro directorio; el instalador acepta `--target`.
Debe apuntar a la carpeta de Piper o quedar vacío para usar el valor predeterminado.
Reiniciá Django después
de instalar. La instalación local no instala la voz en otro servidor.

### Síntesis y límites

`POST /api/v1/voz/`, JSON `{"texto":"consejo exacto de Groq"}`, devuelve
`audio/wav`, PCM16 mono a 22.050 Hz y sin caché. La envolvente del frontend lee
la frecuencia del WAV, por lo que la boca y los controles existentes son compatibles.

Se conservan el proceso aislado por consulta, el bloqueo de una síntesis por
proceso y el límite de 45 segundos. El endpoint admite hasta 600 caracteres
(los consejos actuales de Groq están limitados a 280); el audio no puede superar
90 segundos. Devuelve 429 si está ocupado y 503 si falta el motor, los archivos,
se supera el tiempo o falla la síntesis. No guarda texto/audio ni descarga archivos
durante una consulta.

Piper convierte el texto a fonemas por oración. Cada inferencia recibe hasta
64 símbolos de pronunciación, conservando símbolos compuestos y prefiriendo
límites de palabras. Usa CPU con un hilo de ONNX, sin arena, patrón de memoria ni
prepacking. Los fragmentos se unen en un único WAV, con pausas de 20 ms entre
grupos y 80 ms después de puntuación de cierre. Los arrays se liberan por fragmento
y el proceso termina al finalizar cada consulta.

### Render

Build Command, ejecutado desde la raíz del backend:

```sh
pip install -r requirements.txt && pip install gunicorn && pip install -r requirements-voice.txt && python scripts/install_voice.py
```

Mantener un worker de Gunicorn: el bloqueo de síntesis es por proceso. El mismo
Build Command instala Piper y sus archivos; el worker carga Sharvard. No requiere cambios del
frontend ni otra API key. Para despliegues públicos, aplicar los límites de
solicitudes del proxy como para el resto de la API.

### Medición real

```powershell
.venv\Scripts\python.exe scripts/profile_voice.py
.venv\Scripts\python.exe scripts/profile_voice.py --runs 20
```

En Linux: `python scripts/profile_voice.py --runs 20`. Cada ejecución arranca un
worker nuevo: mide carga del modelo y síntesis, sin Groq ni transporte HTTP.
Informa pico RSS del worker, p50 y p95 (rango más cercano) y guarda una muestra en
`tmp/isa-piper-female-sample.wav`. `--text` permite probar otros consejos.
El pico RSS del proceso no es el consumo total del contenedor. Las medidas locales
no garantizan entrar en 512 MB en Linux: validar Render con textos variados,
concurrencia y arranques en frío.

Medición local en Windows: 20 workers consecutivos con el mismo consejo de 161
caracteres dieron un pico RSS máximo de 200,8 MiB, p50 de 5,58 segundos y p95 de
5,71 segundos, incluyendo arranque y carga del modelo. No es el p95 del endpoint
publicado ni del flujo completo del clima. La generación de voz con Piper ya fue
comprobada en el despliegue gratuito de Render; el rendimiento bajo carga debe
medirse en ese entorno.

En Linux se registran eventos `isa_memory` con `engine: piper`, antes/después de
cargar el modelo, fonemizar e inferir. `rss_mib` y `peak_rss_mib` describen el
proceso; `cgroup_current_mib` y `cgroup_limit_mib`, el contenedor cuando están
disponibles. `tokens` cuenta IDs de entrada, incluidos los símbolos de control
de Piper. No se registran sus contenidos, texto, audio ni credenciales.

### Créditos de voz

- Motor [Piper / Open Home Foundation](https://github.com/OHF-Voice/piper1-gpl), GPL-3.0.
- Modelo Sharvard medium de [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices/raw/5041a7a49ae5b3a0f30e6837769eb03fdbb231bd/es/es_ES/sharvard/medium/MODEL_CARD);
  conservar el MODEL_CARD distribuido con los archivos.
- Corpus Sharvard: Vincent Aubanel, Maria Luisa Garcia Lecumberri y Martin Cooke,
  LISTA Consortium (2014), [doi:10.7488/ds/75](https://doi.org/10.7488/ds/75).
  El MODEL_CARD indica licencia del dataset
  [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/).

## API y pruebas

- `GET /api/v1/health/`: estado del servicio.
- `GET /api/v1/clima/`: clima, pronóstico y recomendación por nombre o coordenadas; admite `idioma=es|en`.
- `GET /api/v1/lugares/`: sugerencias de lugares.
- `GET /api/v1/alertas/`: alertas meteorológicas.

```powershell
.venv\Scripts\python.exe scripts/test_backend.py
```

Las pruebas usan proveedores simulados, sin claves reales, red ni base de datos. El contrato JSON está en [api/contracts](api/contracts/).
