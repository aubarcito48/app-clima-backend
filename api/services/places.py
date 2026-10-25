"""Sugerencias de nombres por prefijo; no consulta clima ni IA."""

import http.client
import json
import re
from urllib.parse import urlencode

from .geocoding import GeocodingFailure, GeocodingRateLimited, _parse_location

MAX_BYTES = 256 * 1024


def _invalid_constant(value):
    raise ValueError('JSON no válido')


def search_places(query):
    parts = [part.strip() for part in query.split(',')]
    params = {'name': query, 'count': 5, 'language': 'es', 'format': 'json'}
    if len(parts) > 1 and re.fullmatch(r'[A-Za-z]{2}', parts[-1]):
        params['countryCode'] = parts.pop().upper()
        params['name'] = ', '.join(parts)
    connection = None
    try:
        connection = http.client.HTTPSConnection('geocoding-api.open-meteo.com', timeout=3)
        connection.connect()
        if connection.sock is None:
            raise GeocodingFailure()
        connection.sock.settimeout(4)
        connection.request('GET', '/v1/search?' + urlencode(params), headers={'Accept': 'application/json'})
        response = connection.getresponse()
        if response.status == 429:
            raise GeocodingRateLimited()
        if response.status != 200:
            raise GeocodingFailure()
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise GeocodingFailure()
        payload = json.loads(body.decode('utf-8'), parse_constant=_invalid_constant)
        if not isinstance(payload, dict) or payload.get('error'):
            raise GeocodingFailure()
        rows = payload.get('results', [])
        if not isinstance(rows, list) or len(rows) > 5:
            raise GeocodingFailure()
        suggestions, seen = [], set()
        for row in rows:
            if not isinstance(row, dict) or type(row.get('id')) is not int or row['id'] <= 0:
                raise GeocodingFailure()
            place = _parse_location({
                'name': row.get('name'), 'country': row.get('country_code'), 'state': row.get('admin1') or None,
                'lat': row.get('latitude'), 'lon': row.get('longitude'),
            })
            if row['id'] not in seen:
                suggestions.append({'id': row['id'], **place.as_candidate()})
                seen.add(row['id'])
        return suggestions
    except (OSError, http.client.HTTPException, ValueError):
        raise GeocodingFailure() from None
    finally:
        if connection is not None:
            connection.close()
