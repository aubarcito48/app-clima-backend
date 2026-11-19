"""Country-specific official RSS/CAP adapters. No keys, scraping or inferred alerts."""

from concurrent.futures import ThreadPoolExecutor, wait
from datetime import timedelta, timezone as dt_timezone
from email.utils import parsedate_to_datetime
import hashlib
import math
import re
import threading
import xml.etree.ElementTree as ET

from django.core.cache import cache
from django.utils import timezone
import httpx

from api.services.alerts.alerts import MAX_BYTES
from api.services.alerts.alerts import _failure_reason
from api.services.alerts.alerts import _iso
from api.services.alerts.alerts import _parse_cap
from api.services.alerts.alerts import _select_notices
from api.services.alerts.alerts import _utc
from api.services.alerts.alerts import _xml

SOURCES = {
    'CL': {
        'nombre': 'Dirección Meteorológica de Chile',
        'url': 'https://www.meteochile.gob.cl/PortalDMC-web/index.xhtml',
        'feed': 'https://archivos.meteochile.gob.cl/portaldmc/rss/rss.php',
        'document': r'https://archivos\.meteochile\.gob\.cl/portaldmc/rss/meteochile_[A-Za-z0-9_-]+_cap\.xml',
        'language': 'es',
    },
    'UY': {
        'nombre': 'Instituto Uruguayo de Meteorología',
        'url': 'https://www.inumet.gub.uy/alerta',
        'feed': 'https://www.inumet.gub.uy/reportes/riesgo/rss.xml',
        'document': r'https://www\.inumet\.gub\.uy/reportes/riesgo/cap_[0-9_]+\.xml',
        'language': 'es',
    },
    'BR': {
        'nombre': 'Instituto Nacional de Meteorologia',
        'url': 'https://avisos.inmet.gov.br/',
        'feed': 'https://apiprevmet3.inmet.gov.br/avisos/rss',
        'document': r'https://apiprevmet3\.inmet\.gov\.br/avisos/rss/[0-9]+',
        'language': 'pt',
    },
}
_locks = {country: threading.Lock() for country in SOURCES}
ERRORS = (httpx.HTTPError, ValueError, ET.ParseError, TypeError, OverflowError)


class ProviderRateLimited(ValueError):
    pass


def _key(country, suffix):
    return f'official-cap-v1-{country}-{suffix}'


def _download(client, country, url):
    if cache.get(_key(country, 'backoff')):
        raise ProviderRateLimited()
    with client.stream('GET', url) as response:
        if response.status_code == 429:
            retry = response.headers.get('Retry-After', '60')
            try:
                delay = int(retry)
            except ValueError:
                try:
                    delay = math.ceil((parsedate_to_datetime(retry) - timezone.now()).total_seconds())
                except (ValueError, TypeError, OverflowError):
                    delay = 60
            cache.set(_key(country, 'backoff'), True, max(60, min(delay, 86400)))
            raise ProviderRateLimited()
        response.raise_for_status()
        chunks, size = [], 0
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError('Oversized official document')
            chunks.append(chunk)
        return b''.join(chunks)


def _reason(error, stage):
    return stage + '_http_429' if isinstance(error, ProviderRateLimited) else _failure_reason(error, stage)


def _load(country, now):
    source = SOURCES[country]
    with httpx.Client(timeout=httpx.Timeout(5, connect=3), trust_env=False, follow_redirects=False,
                      headers={'User-Agent': 'StitchWeather/1.0 (+https://app-clima-ecru.vercel.app/)',
                               'Accept': 'application/rss+xml, application/xml, text/xml'}) as client:
        root = _xml(_download(client, country, source['feed']))
        channel = root.find('channel')
        if root.tag != 'rss' or channel is None:
            raise ValueError('Unexpected official RSS')
        published = parsedate_to_datetime(channel.findtext('lastBuildDate') or channel.findtext('pubDate') or '')
        if published.tzinfo is None or now-published > timedelta(hours=24) or published-now > timedelta(minutes=15):
            raise ValueError('Unverified feed freshness')
        urls, failures = [], {}
        for item in channel.findall('item'):
            url = (item.findtext('link') or '').strip()
            if not re.fullmatch(source['document'], url):
                failures['documento_enlace'] = failures.get('documento_enlace', 0) + 1
            elif url not in urls:
                urls.append(url)
        expected = len(urls)
        if expected > 128:
            failures['documento_limite'] = expected - 128
            urls = urls[:128]

        def document(url):
            key = _key(country, 'document-' + hashlib.sha256(url.encode()).hexdigest())
            saved = cache.get(key)
            if saved is not None:
                return saved['record']
            record = _parse_cap(_download(client, country, url), url, source['language'])
            cache.set(key, {'record': record}, 180)
            return record

        records, verified = [], 0
        # Bounded fan-out and wall time; never wait for an unbounded queued catalog.
        with ThreadPoolExecutor(max_workers=3) as pool:
            tasks = [pool.submit(document, url) for url in urls]
            _, pending = wait(tasks, timeout=16)
            for task in pending:
                task.cancel()
        for task in tasks:
            if task.cancelled():
                continue
            try:
                record = task.result()
                verified += 1
                if record is not None:
                    records.append(record)
            except ERRORS as error:
                reason = _reason(error, 'documento')
                failures[reason] = failures.get(reason, 0) + 1
        pending_count = sum(task.cancelled() for task in tasks)
        return {'records': records, 'partial': bool(failures or pending_count),
                'published': _iso(published.astimezone(dt_timezone.utc)), 'checked': _iso(now),
                'verification': {'esperados': expected, 'verificados': verified,
                                 'pendientes': pending_count, 'fallos': failures}}


def _catalog(country, now):
    key = _key(country, 'catalog')
    previous = cache.get(key)
    if previous is not None:
        age = (now - _utc(previous['checked'])).total_seconds()
        if 0 <= age < (60 if previous['partial'] else 180):
            return previous
    if not _locks[country].acquire(blocking=False):
        raise ValueError('Official catalog refresh pending')
    try:
        if cache.get(_key(country, 'backoff')):
            raise ProviderRateLimited()
        if cache.get(_key(country, 'failure')):
            raise ValueError('Official source temporarily unavailable')
        try:
            result = _load(country, now)
            cache.set(key, result, 900)
            return result
        except ERRORS:
            cache.set(_key(country, 'failure'), True, 60)
            raise
    finally:
        _locks[country].release()


def query_international_alerts(latitude, longitude, country):
    now, source = timezone.now(), SOURCES[country]
    result = {'ubicacion': {'latitud': latitude, 'longitud': longitude, 'pais': country},
              'estado': 'no_disponible', 'alertas': [],
              'fuente': {'nombre': source['nombre'], 'url': source['url'],
                         'consultado_en_utc': _iso(now), 'publicado_en_utc': None}}
    try:
        catalog = _catalog(country, now)
        if now - _utc(catalog['published']) > timedelta(hours=24):
            return result
        notices = _select_notices(catalog['records'], latitude, longitude, now)
        result.update(estado='parcial' if catalog['partial'] or len(notices) > 128 else 'disponible',
                      alertas=notices[:128])
        result['fuente'].update(consultado_en_utc=catalog['checked'], publicado_en_utc=catalog['published'],
                                verificacion=catalog['verification'])
    except ERRORS as error:
        result['fuente']['verificacion'] = {'fallos': {_reason(error, 'indice'): 1}}
    return result
