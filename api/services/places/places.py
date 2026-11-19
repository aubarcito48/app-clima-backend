"""Our indexed local autocomplete. No network, API keys, AI or user persistence."""

from contextlib import closing
import re
import sqlite3

from api.services.places.geocoding import GeocodingFailure
from api.services.places.place_catalog import catalog_uri
from api.services.places.place_catalog import normalize_name

RESULT_LIMIT = 5


def search_places(query):
    parts = [part.strip() for part in query.split(',')]
    country = parts.pop().upper() if len(parts) > 1 and re.fullmatch('[A-Za-z]{2}', parts[-1]) else None
    name = normalize_name(parts[0])
    region = normalize_name(', '.join(parts[1:]))
    if len(name) < 3:
        return []
    # BINARY prefix ranges use the names primary index, including non-Latin text.
    statement = '''
        SELECT c.id, c.name, c.country, c.region, c.latitude, c.longitude,
               min(CASE WHEN n.name = ? THEN 0 ELSE 1 END) AS match_rank
        FROM names n JOIN cities c ON c.id = n.city_id
        WHERE n.name >= ? AND n.name < ?
    '''
    parameters = [name, name, name + '\U0010ffff']
    if country:
        statement += ' AND c.country = ?'
        parameters.append(country)
    if region:
        statement += ' AND c.region_key >= ? AND c.region_key < ?'
        parameters.extend([region, region + '\U0010ffff'])
    statement += ''' GROUP BY c.id
        ORDER BY CASE WHEN match_rank = 0 THEN 0
                      WHEN c.name_key >= ? AND c.name_key < ? THEN 1
                      ELSE 2 END,
                 c.population DESC, c.name, c.country, c.id LIMIT ?'''
    parameters.extend([name, name + '\U0010ffff', RESULT_LIMIT])
    try:
        with closing(sqlite3.connect(catalog_uri(), uri=True, timeout=1)) as connection:
            rows = connection.execute(statement, parameters).fetchall()
    except (OSError, sqlite3.Error):
        raise GeocodingFailure() from None
    return [dict(zip(('id', 'nombre', 'pais', 'region', 'latitud', 'longitud'), row[:6])) for row in rows]
