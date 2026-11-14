# Fase 3: ensayo de Rhubarb antes de cambiar la boca de Isa

Rhubarb 1.14.0 analiza el WAV final de Piper, incluidas sus pausas, volumen y
ritmo. Produce tiempos y formas de boca; no imágenes. Esta entrega incorpora
**el ensayo acústico y de recursos**, no una nueva animación facial. El catálogo
actual conserva su bucle continuo. La integración visual y la revisión de
naturalidad quedan pendientes de tener imágenes alineadas.

## Activar o desactivar

`ISA_LIP_SYNC=off` es el valor predeterminado y conserva el comportamiento anterior.
Con `ISA_LIP_SYNC=rhubarb`, la síntesis sigue estos pasos:

1. Piper termina de sintetizar y su proceso sale.
2. Dentro del mismo bloqueo de voz, Rhubarb analiza el WAV con `phonetic`, un hilo
   y formas A–F/G/H/X. No se mantiene un modelo adicional residente.
3. Se validan los tiempos y se agrega un chunk RIFF opcional `isav` con solo
   `start`, `end`, `value`; se omite la ruta `soundFile` del JSON de Rhubarb.
4. Si falta el ejecutable, falla o agota su presupuesto, se devuelve el WAV
   original. No se consulta Groq otra vez ni se pierde el consejo por ese fallo.

Después del primer timeout en Render a los ocho segundos, la prueba se amplió:
Piper conserva sus 45 segundos y Rhubarb dispone de un presupuesto independiente
de hasta 60 segundos. `ISA_RHUBARB_TIMEOUT_SECONDS` permite elegir de 1 a 60,
con 60 por defecto. La espera HTTP del frontend es de 120 segundos y el archivo
`gunicorn.conf.py` fija 130 segundos para el servidor. Si el Start Command o
`GUNICORN_CMD_ARGS` define un `--timeout` menor, prevalece: usar al menos 130
para esta prueba. No es necesario ocupar todo ese tiempo: se devuelve el WAV
apenas termina el análisis. Estos límites no garantizan rendimiento en CPU
limitada. El proceso se mata y recoge
al agotar su tiempo. Un OOM que mate el contenedor entero no admite fallback:
desactivar la variable o revertir el commit si la prueba en Render resulta mal.

`isav` contiene hasta 1.500 marcas y 64 KiB; `isac` sigue guardando la actuación
por fragmentos. Ambos son chunks opcionales de un WAV estándar. El frontend actual
ignora `isav` y reproduce el mismo PCM. No debe presentarse el éxito de este
análisis como una mejora visual ya terminada.

## Instalación y muestra local

Desde la raíz del backend:

```powershell
.\.venv\Scripts\python.exe scripts/install_rhubarb.py
```

Agregar `ISA_LIP_SYNC=rhubarb` al `.env`, reiniciar el backend y ejecutar:

```powershell
.\.venv\Scripts\python.exe scripts/probe_lip_sync.py
.\.venv\Scripts\python.exe scripts/probe_lip_sync.py --language en --output tmp/isa-rhubarb/probe-en.wav
```

No llama a OpenWeather ni Groq. Crea un WAV y un HTML local con reproductor y
línea de tiempo; abrir el HTML y escuchar las marcas. No dibuja un rostro nuevo.
Para un WAV existente que ya tenga el chunk `isav`:

```powershell
.\.venv\Scripts\python.exe scripts/preview_lip_sync.py tmp/isa-rhubarb/es_long.wav
```

El instalador usa los ZIP oficiales de Windows/Linux x86-64, con versión, tamaño
y SHA256 fijados. Instala ejecutable, recursos y licencia; excluye demos y tests.
Los binarios quedan en `models/`, fuera de Git. `--from-zip` permite reutilizar
una descarga verificada. En otros sistemas/arquitecturas se detiene explícitamente.

## Ensayo en Render

Agregar **`ISA_LIP_SYNC=rhubarb`** a Environment y usar Save, rebuild and deploy
con este commit publicado. El Build Command existente termina con
`python scripts/install_voice.py`; este script instala Rhubarb cuando encuentra
esa variable. No hace falta cambiar el comando ni agregar claves. Una variable
definida después del build requiere reconstruir para instalar el binario.

Tras el despliegue, generar un consejo nuevo y dejar terminar la voz. Buscar
`isa_memory` con **`engine: rhubarb`**:

- `processing_start`: empieza después de que sale Piper.
- `complete`: `mouth_cues`, `elapsed_seconds`, `peak_cgroup_observed_mib`.
- `timeout`, `failed`, `missing_binary`, `skipped_budget`: conserva el audio original.

Se muestrea el consumo del contenedor cada 50 ms durante Rhubarb. El máximo es
observado, no un pico instantáneo garantizado. El RSS del evento pertenece al
proceso Python que registra; para el consumo total usar los campos `cgroup`.
No sumar RSS a cgroup. Las mediciones de Piper y Rhubarb son secuenciales: no
se deben sumar sus máximos como si ambos modelos estuvieran en RAM a la vez.

Los eventos de Rhubarb incluyen `timeout_seconds` para verificar el presupuesto
activo. La primera prueba en Render terminó por timeout a los 8,081 s, con
202,5 MiB de máximo observado durante Rhubarb y 314,6 MiB visibles durante Piper:
se amplió el tiempo para medir si el reconocedor puede completar su trabajo.

Comparar con el máximo de 284,3 MiB observado en las capturas de Piper del
14/11/2026, límite 512 MiB, y unos 29 s entre inicio y fin de aquella síntesis.
Esa muestra aislada no es el límite de consumo de todos los textos.

Para volver al flujo anterior, `ISA_LIP_SYNC=off` y reiniciar/desplegar. También
se puede revertir este commit. No se modifican imágenes ni datos persistentes.

## Medición local del 14/11/2026

Windows, backend con un servidor Django aislado, petición de voz completa con
saludo y despedida, director local, un hilo de Rhubarb. Pico del árbol muestreado
cada 25 ms, sin incluir el navegador. No equivale a memoria Linux/cgroup.

| Muestra | Audio | Marcas | Petición total | Pico observado del árbol |
| --- | ---: | ---: | ---: | ---: |
| Español corto | 4,66 s | 39 | 6,157 s | 254,96 MiB |
| Español largo | 13,87 s | 95 | 7,725 s | 280,26 MiB |
| Inglés largo | 13,26 s | 85 | 7,246 s | 274,74 MiB |

Todas dieron HTTP 200 y metadata válida. Una prueba separada de Rhubarb solo,
con audio de 4,70 s, tardó 0,836 s y observó 72,41 MiB de working set. No se
garantiza que ese consumo o demora se repitan con otros audios o en Render Free.
La medición previa sin Rhubarb no usó exactamente el mismo PCM; comparar esos
totales orienta, pero no atribuye diferencias de memoria al cambio.

## Próximo paso visual

Usar el [catálogo de nueve formas para Gemini](GEMINI.md). Revisar estabilidad
de rostro, encuadre y cabeza entre imágenes. Después conectar `isav` al reloj
real del audio en un prototipo visual separado y comparar con el mismo WAV.
No saltar entre fotogramas completos de distintas poses ni afirmar que las
seis/nueve formas equivalen a fonemas exactos del español.

Rhubarb es MIT; se conserva su `LICENSE.md` con los avisos de sus dependencias.
[Proyecto oficial](https://github.com/DanielSWolf/rhubarb-lip-sync).
