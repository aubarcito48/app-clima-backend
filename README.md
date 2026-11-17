# App Clima Backend

API de la app del clima, desarrollada con Python y Django. Resuelve ubicaciones, consulta el clima y pronóstico de OpenWeather, y genera recomendaciones con Groq en español o inglés. No guarda datos de usuarios. Las sugerencias usan un catálogo geográfico local de solo lectura, sin API externa.

## Protección del uso de IA

Caché en memoria de consejos válidos por 5 minutos y límites por visitante,
además del límite global por minuto.
El mismo modelo y director siguen generando los consejos. La caché incluye idioma,
contexto meteorológico, prompt y configuración: no mezcla español e inglés.
No hay reintentos del SDK; los fallos tienen una pausa por clave de 30 segundos.
Si Groq falla o limita su uso, el clima sigue disponible y la IA devuelve `no_disponible`.

Compatible con **Render Free**, sin disco, base de datos ni variables adicionales.
Se eliminó el contador diario persistente: no hay un presupuesto global diario propio.
La caché y los límites por minuto son por proceso y se reinician con él.
Ver [configuración, pruebas y límites de la protección](docs/GROQ-USAGE-GUARD.md).

## Mapas y alertas oficiales

El frontend abre un mapa automáticamente junto a las alertas: temperatura, lluvia
y viento mediante Weather Maps 1.0. `GET /api/v1/mapa/` actúa como proxy fijo de
imágenes PNG; usa la clave existente de OpenWeather sin entregarla al navegador.
Mantiene hasta 32 imágenes por proceso durante cinco minutos y corta ráfagas
cuando el proveedor falla. Límites iniciales: 40 solicitudes/minuto por proceso
y 24 por visitante. No requiere disco, variables nuevas ni llamadas a Groq.
El mapa base utiliza OpenStreetMap con atribución visible; no se carga antes de
seleccionar una ciudad. Se puede cerrar manualmente.

El catálogo SMN admite hasta 256 documentos únicos e incluye la ruta oficial
`avisocortoplazo`, además de las alertas generales. Se conserva el estado parcial
si un documento falla, se supera el límite o no termina a tiempo. Las consultas
comparten catálogo por tres minutos (30 segundos si fue parcial), sin duplicar
descargas concurrentes dentro del proceso. Los documentos válidos se conservan
una hora para reintentar solo los faltantes. Las descargas van espaciadas y un
HTTP 429 detiene nuevas solicitudes durante el backoff. La tarjeta diferencia
este límite del SMN de otros fallos. En producción, una única recuperación en
segundo plano intenta completar los documentos faltantes con un presupuesto
de cuatro minutos por ejecución, sin saltarse el backoff. No requiere otra visita
ni un servicio contratado. La caché del catálogo completo sigue siendo de tres
minutos; cada consulta revalida las vigencias y el catálogo renovado incorpora
las actualizaciones y cancelaciones.
Los textos oficiales conservan español.

## Buscador local de ciudades

`GET /api/v1/lugares/?q=Cordoba,AR` consulta nuestro índice de nombres y alias,
sin conexión a Open-Meteo ni a GeoNames. Conserva el contrato público y limita
la respuesta a cinco localidades. Reconoce acentos, alias y filtros de región
y país ISO de dos letras. Los nombres exactos se ordenan primero y la población
desempata; se excluyen alias ambiguos de tres letras mayúsculas.

El [catálogo y su procedencia](data/README.md) se incluyen en el repositorio.
No hay descargas durante el arranque o las consultas. No requiere un servicio
de base de datos ni un disco persistente para el buscador: su SQLite es un índice
estático abierto con `mode=ro&immutable=1`, separado de la caché de IA.

Los consejos en español usan voseo y vocabulario argentino cotidiano, priorizando
formas como «Usá una campera liviana», «llevá» y «elegí», sin exagerar el lunfardo.
Esta dirección de escritura es independiente del origen de la voz de Piper. En
inglés se reemplaza el bloque de estilo completo para no mezclar vocabulario ni
formas verbales españolas. No se reemplazan palabras después de generar el consejo,
preservando su coherencia con la síntesis de voz y la animación. Por defecto Groq
genera también la actuación; el modo local de prueba la calcula con reglas.

Frontend: [StitchWeather](https://github.com/aubarcito48/app-clima).

## Interpretación de Isa por fragmentos

`ISA_DIRECTOR=groq` conserva el director actual. `ISA_DIRECTOR=local` pide a Groq
solo el consejo y calcula los mismos segmentos en Python, sin otra consulta ni
modelo adicional. Es una opción de prueba: requiere reiniciar el backend y obtener
un consejo nuevo; no cambia un consejo que el navegador ya haya cargado.
Ver [prueba comparativa y límites](docs/isa-local/PHASE-2.md) y
[recursos para Gemini](docs/isa-local/GEMINI.md).

El director local tiene [reglas separadas para español e inglés](docs/isa-local/LANGUAGE-DIRECTORS.md):
la interfaz sigue siendo la misma y el español conserva su comportamiento aprobado.
Los ajustes ingleses se pueden calibrar independientemente en su propio módulo.

El [clasificador propio RF V2](docs/isa-local/OWN-PRODUCTION.md) usa los fonemas y
tiempos de la misma síntesis de Piper. `ISA_LIP_SYNC=own` es el valor predeterminado.
La inferencia corre después de Piper y agrega marcas al WAV. El valor heredado
`rhubarb` también selecciona el motor propio; Rhubarb ya no se ejecuta en la ruta
de voz. Los ensayos históricos se conservan como referencia.

Groq devuelve JSON con `texto` y `segmentos`: entre uno y cuatro fragmentos que,
unidos con un espacio, deben reproducir exactamente el consejo. Cada fragmento
elige `gesture` del catálogo real (`isa-awake`, `isa-right`, `isa-down`), `speed`
entre 0.8 y 1.2, `energy` entre 0.65 y 1.2 y `pause_ms` entre 0 y 600.
No se importan expresiones de Aubar ni del antiguo avatar SVG.

`recomendacion.segmentos` es opcional para consumidores anteriores. Groq dispone
de al menos 512 tokens para consejo y dirección (1024 con GPT-OSS); el consejo
conserva el límite de 280 caracteres y 40 palabras. Los planes inválidos no se
ejecutan. El frontend también puede leer recomendaciones anteriores sin plan.

`POST /api/v1/voz/` admite `segmentos` opcionales con el mismo texto completo
normalizado, hasta seis para incluir saludo y despedida. Piper carga un único
modelo en un worker y sintetiza cada fragmento con su ritmo, volumen y pausa.
El WAV sigue siendo PCM16 mono y lleva un chunk RIFF opcional `isac` con
`from`, `speech_end`, `until` (segundos calculados a partir de muestras reales)
y `gesture`. No se necesitan cabeceras CORS nuevas ni una segunda petición.
Se mantienen los límites de concurrencia, duración y tiempo de síntesis.

La energía controla volumen, no una emoción vocal nativa. Las miradas usan las
animaciones existentes; los tiempos son por fragmento, no por fonema.

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
.venv\Scripts\python.exe -m pip install --upgrade pip==26.2.2
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe scripts/create_local_env.py
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

El script crea `.env` con un secreto de Django y conserva el archivo si ya existe. Configurá allí `OPENWEATHER_API_KEY`, `GROQ_API_KEY` y `GROQ_MODEL` para usar los proveedores. Las demás opciones están en [.env.example](.env.example). No se requieren migraciones.

## Voz de Isa

Se restauró Sharvard después de probar Daniela argentina high. En el backend
publicado, una narración de 254 caracteres con Daniela devolvió 503 a los 45,8
segundos, coincidiendo con el límite del worker. No se pudo confirmar si también
hubo presión de memoria sin los registros de Render. Se mantienen las animaciones
de habla del frontend y, en esa etapa, Lessac para inglés; esa restauración cambió solo la voz
española y su instalación.

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

También se instala `en_GB-cori-medium`, voz de Cori Samuel en inglés británico.
La selección final conserva Sharvard en español y usa Cori con `length_scale` × 1,08
para el inglés más pausado, además del ritmo del director local.
Se carga únicamente el modelo del idioma solicitado, con la misma concurrencia de uno.
El directorio conserva su nombre `models/piper-sharvard` y contiene ambos modelos.

`POST /api/v1/voz/`, JSON `{"texto":"consejo exacto de Groq","idioma":"es"}`, devuelve
`audio/wav`, PCM16 mono a 22.050 Hz y sin caché. La envolvente del frontend lee
la frecuencia del WAV, por lo que la boca y los controles existentes son compatibles.
`idioma` es opcional (`es` por defecto) y admite únicamente `es` o `en`.
En inglés, `°C` y `km/h` se pronuncian como `degrees` y `kilometers per hour`.

Se conservan el proceso aislado por consulta, el bloqueo de una síntesis por
proceso y el límite de 45 segundos. El endpoint admite hasta 600 caracteres
(los consejos actuales de Groq están limitados a 280); el audio no puede superar
90 segundos. Devuelve 429 si está ocupado y 503 si falta el motor, los archivos,
se supera el tiempo o falla la síntesis. No guarda texto/audio ni descarga archivos
durante una consulta.

Solo para la pronunciación, las temperaturas como `19 °C` se convierten en
`19 grados` (o `1 grado`); Isa omite la letra C. El consejo mostrado conserva
su texto y sus unidades originales. Del mismo modo, `km/h` se pronuncia
`kilómetros por hora` sin cambiar la abreviatura mostrada en la tarjeta.
Piper convierte el texto a fonemas por oración. Cada inferencia recibe hasta
64 símbolos de pronunciación, conservando símbolos compuestos y prefiriendo
límites de palabras. Usa CPU con un hilo de ONNX, sin arena, patrón de memoria ni
prepacking. Los fragmentos se unen en un único WAV, con pausas de 20 ms entre
grupos y 80 ms después de puntuación de cierre. Los arrays se liberan por fragmento
y el proceso termina al finalizar cada consulta.

### Render

Build Command, ejecutado desde la raíz del backend:

```sh
python -m pip install --upgrade pip==26.2.2 && python -m pip install -r requirements-production.txt && python scripts/install_voice.py
```

Con `ISA_LIP_SYNC=own`, el build prepara copias de las voces con salida de
duraciones, sin modificar los archivos originales. No descarga Rhubarb.
Ver [activación, métricas y vuelta atrás](docs/isa-local/OWN-PRODUCTION.md).

El clasificador propio tiene hasta 30 segundos independientes de los
45 de Piper. El frontend espera
120 segundos y `gunicorn.conf.py` configura 130. Si el Start Command contiene
un `--timeout` explícito, usar al menos 130 porque ese argumento prevalece.

Mantener un worker de Gunicorn: el bloqueo de síntesis es por proceso. El mismo
Build Command instala ambos modelos; el worker carga Sharvard o Cori según el idioma.
No requiere otra API key. Para despliegues públicos, aplicar los límites de
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
- Modelo inglés [Cori medium](https://huggingface.co/rhasspy/piper-voices/blob/e9ab671f2a0e50a701b34361136ba3e6a3a9eb0c/en/en_GB/cori/medium/MODEL_CARD),
  voz de Cori Samuel, corpus HiFi-TTS de NVIDIA, CC BY 4.0 según su ficha.
  Se conserva `MODEL_CARD.en` junto al modelo; descarga y hashes fijados en el instalador.
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

Las pruebas usan proveedores simulados, sin claves reales ni red. Solo se permite abrir el catálogo geográfico fijo en modo de solo lectura; no se permiten bases de datos de usuarios. El contrato JSON está en [api/contracts](api/contracts/).

## Seguridad y presupuestos de solicitudes

En producción se aplica una ventana móvil de 60 segundos por proceso: clima 30,
lugares 120, alertas 60 y voz 6 solicitudes. Son presupuestos globales compartidos,
no límites por usuario. Se configuran con `API_*_REQUESTS_PER_MINUTE` en `.env.example`.
Las respuestas 429 incluyen `Retry-After`; salud y preflight CORS no consumen cuota.
Se mantiene un worker de Gunicorn y una síntesis simultánea. Con varios workers
estos límites se multiplican: haría falta un limitador compartido o en el proxy.

La voz lee como máximo 8193 bytes antes de rechazar cuerpos de más de 8192,
rechaza claves JSON duplicadas y caracteres de control, invisibles o Unicode
inválido. Las consultas de la API se limitan a 2048 caracteres antes de invocar
proveedores. CORS no autentica clientes ni detiene scripts externos. El límite
local reduce el consumo, pero no sustituye protección contra DDoS en el proxy/CDN.

Ver alcance, evidencias y limitaciones en [SECURITY_REVIEW.md](SECURITY_REVIEW.md).
