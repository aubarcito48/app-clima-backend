# Catálogo local de localidades

Datos de **GeoNames**, snapshot descargado el 16/11/2026.
Fuente: <https://download.geonames.org/export/dump/>.
Licencia del extracto: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Gracias a GeoNames y a sus colaboradores. Los datos se ofrecen sin garantía
de exactitud, actualidad o exhaustividad.

`places.sqlite` es un índice estático de solo lectura, no almacena búsquedas,
IP, favoritos ni información de visitantes. El motor de búsqueda es propio.
Incluye el extracto `cities1000` (localidades de más de 1000 habitantes y algunas
cabeceras administrativas) y las regiones de `admin1CodesASCII`. **No contiene
todas las aldeas del mundo.** Si falta una localidad, se puede seguir buscando
manualmente con Enter: la consulta del clima conserva su geocodificación de OpenWeather.

Cambios respecto de los datos originales: selección de campos, normalización
Unicode para búsqueda, deduplicación de alias y exclusión de abreviaciones
ambiguas de tres mayúsculas. Los nombres mostrados conservan sus caracteres
originales; algunos nombres de regiones están en inglés. La fecha, cantidades,
URLs y hashes SHA-256 están en `places.manifest.json`.

Para reconstruir con los archivos descargados en `tmp/place-catalog`:

```powershell
.\.venv\Scripts\python.exe scripts/build_place_catalog.py
```

`--download` permite obtener los archivos si faltan. El script comprueba los
hashes del snapshot y rechaza descargas distintas: actualizar los hashes exige
revisar explícitamente los datos nuevos. El despliegue utiliza el catálogo
versionado; no ejecuta este script ni necesita una clave de GeoNames.

El crédito a GeoNames también aparece junto a las sugerencias del buscador.
Open-Meteo dejó de participar en el autocompletado.
