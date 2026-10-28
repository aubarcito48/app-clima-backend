# App Clima Backend

API de la app del clima, desarrollada con Python y Django. Resuelve ubicaciones, consulta el clima y pronóstico de OpenWeather, y genera recomendaciones con Groq en español o inglés. No utiliza base de datos.

Frontend: [StitchWeather](https://github.com/aubarcito48/app-clima).

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

Para reutilizar los modelos descargados de Aubar:

```powershell
.venv\Scripts\python.exe scripts/install_voice.py --from-dir ../../botbar/models/kokoro-v1.0
```

El instalador verifica tamaño y SHA256. Los modelos quedan fuera de Git.
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

## API y pruebas

- `GET /api/v1/health/`: estado del servicio.
- `GET /api/v1/clima/`: clima, pronóstico y recomendación por nombre o coordenadas; admite `idioma=es|en`.
- `GET /api/v1/lugares/`: sugerencias de lugares.
- `GET /api/v1/alertas/`: alertas meteorológicas.

```powershell
.venv\Scripts\python.exe scripts/test_backend.py
```

Las pruebas usan proveedores simulados, sin claves reales, red ni base de datos. El contrato JSON está en [api/contracts](api/contracts/).
