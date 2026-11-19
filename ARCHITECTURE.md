# Organización del backend

La aplicación Django sigue siendo `api`, con `config` para la configuración del
proyecto. Dentro de cada capa, los archivos se agrupan por funcionalidad.

```text
api/
  urls.py                       Contrato público /api/v1/
  views/
    weather.py                  Consulta del clima
    places.py                   Búsqueda de lugares
    alerts.py                   Alertas oficiales
    maps.py                     Proxy de mapas
    voice.py                    Audio opcional de Isa
    health.py                   Liveness
    errors.py                   Respuesta pública de error 500
  validation/
    weather.py                  Consultas por ciudad o coordenadas
    places.py                   Búsqueda de lugares
    alerts.py                   Coordenadas y país de las alertas
    fields.py                   Normalización de texto común
  services/
    weather/                    Orquestación y datos meteorológicos
    places/                     Geocodificación y catálogo local
    alerts/                     Fuentes nacionales e internacionales
    providers/                  Transporte compartido de OpenWeather
    assistant/
      recommendations.py        Consejos y disponibilidad parcial
      groq_guard.py             Presupuesto y protección del proveedor
      direction/                Dirección ES/EN y metadatos de interpretación
      voice/                    Piper, proceso de síntesis y fragmentos de voz
      alignment/                Sincronización labial
        isa_ml/                 Inferencia y pesos versionados
  tests/
    weather/ places/ alerts/ maps/ assistant/ http/ configuration/
  contracts/                    Esquemas y ejemplos públicos, sin cambios
```

`apps.py`, `management/`, `responses.py`, `request_limits.py` y `operational.py`
conservan sus ubicaciones: son integración Django y utilidades transversales.
No se añaden aplicaciones, modelos de base de datos ni migraciones.

## Dependencias

- Las vistas validan entradas y llaman a servicios; los errores públicos se
  construyen con `responses.py`.
- `services/weather/climate.py` coordina geocodificación, clima y recomendaciones.
- Clima y geocodificación comparten `services/providers/openweather.py`.
- Las recomendaciones usan el snapshot meteorológico y la dirección de Isa;
  la consulta conserva su respuesta parcial cuando falla un proveedor.
- El servicio de voz ejecuta `assistant/voice/voice_worker.py` por separado;
  la inferencia labial también conserva su proceso y límites existentes.
- El catálogo sigue en `data/places.sqlite`, los modelos Piper en `models/` y
  los pesos de inferencia junto al paquete `isa_ml`. Se ajustan las rutas
  calculadas desde `__file__` al mover sus consumidores.

## Convenciones de mantenimiento

Los imports internos apuntan al módulo concreto, sin reexportaciones que oculten
dependencias. Los `__init__.py` permiten descubrir paquetes y pruebas en Django.

Colocar cada nueva prueba en el grupo correspondiente y mantener los mocks
apuntando al módulo donde se utiliza la dependencia. Los esquemas de `contracts/`
continúan siendo comunes a todas las funcionalidades.

Las rutas HTTP, nombres de URL, configuración del entorno y comandos de arranque
se conservan. Los scripts y experimentos actualizan sus imports y rutas de código;
los datos, audios y resultados históricos no se regeneran.
