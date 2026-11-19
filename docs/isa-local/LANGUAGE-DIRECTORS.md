# Directores locales separados por idioma

Separación local solicitada por Nahuel para poder calibrar Cori sin modificar
la interpretación española que ya aprobó.

- `api/services/assistant/direction/isa_director_es.py`: reglas españolas existentes, sin cambios de
  palabras clave, gesto, velocidad, energía o pausa.
- `api/services/assistant/direction/isa_director_en.py`: reglas inglesas independientes y parámetros
  de entrega propios, inicialmente con los valores anteriores.
- `api/services/assistant/direction/isa_director_shared.py`: limpieza y límites de fragmentos; no
  contiene parámetros de voz ni decisiones de interpretación por idioma.
- `api/services/assistant/direction/isa_local_director.py`: mantiene la interfaz pública
  `direct_locally(text, language=...)` y selecciona el director correspondiente.

No hace falta agregar variables: `ISA_DIRECTOR=local` continúa funcionando.
Las recomendaciones, pruebas de voz y generadores importan la misma interfaz.
No se cambia Piper, la voz de Cori, Sharvard, el formato JSON ni los clientes.

La extracción conserva deliberadamente el comportamiento de ambos idiomas.
Se verificó equivalencia exacta con la versión previa en 680 combinaciones de
frases españolas e inglesas, incluidas advertencias, referencias temporales,
decimales y agrupación al límite de fragmentos. Una prueba permanente modifica
velocidad/pausa del director inglés y exige que la salida española siga idéntica.

Esta separación permite calibrar inglés de forma independiente; no constituye
una corrección perceptual de la sincronización. El renderizador sigue usando
secuencias completas, Rhubarb y el reloj del audio. Los gestos por fragmento del
director no se conectan automáticamente al retrato: hace falta evaluar esa
integración sin perjudicar la continuidad facial.

La comparación de Cori 1,08/1,20/1,30 y el reloj de pausas permanece aislada en
el frontend. No se activa al separar los módulos. Sin push ni cambios en la
aplicación publicada.

El siguiente ensayo añade un [perfil inglés pausado optativo](ENGLISH-PACED-PROFILE.md),
sin cambiar el perfil activo. Ese documento registra también la corrección puntual
de lectura de grados en español e inglés.
