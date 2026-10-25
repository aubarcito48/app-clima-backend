"""Official SMN CAP notices, filtered by geometry and validity; no risk inference."""

from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timedelta, timezone as dt_timezone
from email.utils import parsedate_to_datetime
import math
import re
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from django.core.cache import cache
from django.utils import timezone
import httpx

FEED = "https://ssl.smn.gob.ar/CAP/AR.php"
SOURCE = "https://www.smn.gob.ar/alertas"
NS = {"c": "urn:oasis:names:tc:emergency:cap:1.2"}
MAX_BYTES = 1024 * 1024
CACHE_KEY = "smn-cap-catalog-v1"
MAX_DOCUMENTS = 32


def _utc(value):
    date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if date.tzinfo is None:
        raise ValueError("Missing timezone")
    return date.astimezone(dt_timezone.utc)


def _iso(date):
    return date.isoformat().replace("+00:00", "Z")


def _xml(body):
    if len(body) > MAX_BYTES or b"<!DOCTYPE" in body.upper() or b"<!ENTITY" in body.upper():
        raise ValueError("Unsafe or oversized XML")
    return ET.fromstring(body)


def _cap_url(value):
    url = urlsplit(value)
    if url.scheme != "https" or url.netloc != "ssl.smn.gob.ar" or url.query or url.fragment:
        raise ValueError("Untrusted CAP URL")
    if not re.fullmatch(r"/feeds/CAP/(?:xml_generados|cap_salida)/[A-Za-z0-9_.-]+\.xml", url.path):
        raise ValueError("Unexpected CAP path")
    return value


def _point(value):
    latitude, longitude = map(float, value.split(","))
    if not math.isfinite(latitude) or not math.isfinite(longitude) or not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Invalid point")
    return latitude, longitude


def _geometry(area):
    shapes = []
    for element in area.findall("c:polygon", NS):
        points = [_point(value) for value in (element.text or "").split()]
        if not 4 <= len(points) <= 10000 or points[0] != points[-1]:
            raise ValueError("Invalid polygon")
        shapes.append(("polygon", points))
    for element in area.findall("c:circle", NS):
        center, radius = (element.text or "").split()
        radius = float(radius)
        if not math.isfinite(radius) or not 0 <= radius <= 20002:
            raise ValueError("Invalid circle")
        shapes.append(("circle", (_point(center), radius)))
    if not shapes:
        raise ValueError("No geographic coverage")
    return shapes


def _inside(latitude, longitude, shape):
    kind, points = shape
    if kind == "circle":
        (lat, lon), radius = points
        a, b = math.radians(latitude), math.radians(lat)
        distance = math.sin((a-b)/2)**2 + math.cos(a)*math.cos(b)*math.sin(math.radians(longitude-lon)/2)**2
        return 6371.0088 * 2 * math.asin(math.sqrt(min(1, distance))) <= radius
    inside = False
    for (y1, x1), (y2, x2) in zip(points, points[1:]):
        cross = (longitude-x1)*(y2-y1) - (latitude-y1)*(x2-x1)
        if abs(cross) < 1e-9 and min(x1,x2)-1e-9 <= longitude <= max(x1,x2)+1e-9 and min(y1,y2)-1e-9 <= latitude <= max(y1,y2)+1e-9:
            return True
        if (y1 > latitude) != (y2 > latitude) and longitude < (x2-x1)*(latitude-y1)/(y2-y1)+x1:
            inside = not inside
    return inside


def _text(node, name, *, required=False, limit=20000):
    value = (node.findtext("c:" + name, default="", namespaces=NS) or "").strip()
    if len(value) > limit or (required and not value):
        raise ValueError("Invalid CAP field")
    return value


def _parse_cap(body, url):
    root = _xml(body)
    if root.tag != "{" + NS['c'] + "}alert":
        raise ValueError("Unexpected CAP document")
    if _text(root, "status") != "Actual" or _text(root, "scope") != "Public":
        return None
    identifier = _text(root, "identifier", required=True, limit=512)
    kind = _text(root, "msgType")
    if kind not in {"Alert", "Update", "Cancel"}:
        return None
    sent = _utc(_text(root, "sent", required=True))
    references = []
    for reference in _text(root, "references").split():
        fields = reference.split(",")
        if len(fields) != 3:
            raise ValueError("Invalid CAP references")
        references.append(fields[1])
    result = {"id": identifier, "sent": sent, "references": references, "cancel": kind == "Cancel", "notices": []}
    if result['cancel']:
        return result
    infos = root.findall("c:info", NS)
    spanish = [info for info in infos if _text(info, 'language').lower().startswith('es')]
    for info in spanish or infos[:1]:
        start = _utc(_text(info, "onset") or _text(info, "effective") or _iso(sent))
        end = _utc(_text(info, "expires", required=True))
        if end <= start:
            raise ValueError("Invalid CAP period")
        areas = info.findall("c:area", NS)
        shapes = [shape for area in areas for shape in _geometry(area)]
        if not shapes:
            raise ValueError("Missing CAP areas")
        severity = _text(info, "severity")
        if severity not in {"Extreme", "Severe", "Moderate", "Minor", "Unknown"}:
            raise ValueError("Invalid severity")
        result['notices'].append({
            "identificador": identifier,
            "fenomeno": _text(info, "event", required=True, limit=200),
            "severidad": severity,
            "urgencia": _text(info, "urgency", limit=100),
            "certeza": _text(info, "certainty", limit=100),
            "inicio_utc": _iso(start), "fin_utc": _iso(end), "emitido_en_utc": _iso(sent),
            "descripcion": _text(info, "description", required=True),
            "recomendaciones": _text(info, "instruction"),
            "zona": "; ".join(filter(None, (_text(area, 'areaDesc', limit=3000) for area in areas)))[:5000] or "Área delimitada por el SMN",
            "url": url, "shapes": shapes,
        })
    if not result['notices']:
        raise ValueError("Missing CAP information")
    return result


def _download(client, url):
    with client.stream("GET", url, headers={"Accept": "application/xml, text/xml, application/rss+xml"}) as response:
        response.raise_for_status()
        chunks, size = [], 0
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError("Oversized source document")
            chunks.append(chunk)
        return b"".join(chunks)


def _load_catalog(now):
    with httpx.Client(timeout=httpx.Timeout(3, connect=2), follow_redirects=False) as client:
        root = _xml(_download(client, FEED))
        channel = root.find('channel')
        if root.tag != 'rss' or channel is None:
            raise ValueError("Unexpected feed")
        published = parsedate_to_datetime(channel.findtext('lastBuildDate') or channel.findtext('pubDate') or '')
        if published.tzinfo is None or now-published > timedelta(hours=24) or published-now > timedelta(minutes=15):
            raise ValueError("Outdated feed")
        items = channel.findall('item')
        partial = len(items) > MAX_DOCUMENTS
        urls = []
        for item in items[:MAX_DOCUMENTS]:
            try:
                url = _cap_url(item.findtext('link') or '')
                if url not in urls:
                    urls.append(url)
            except ValueError:
                partial = True
        def document(url):
            return _parse_cap(_download(client, url), url)
        with ThreadPoolExecutor(max_workers=6) as pool:
            tasks = [pool.submit(document, url) for url in urls]
            done, pending = wait(tasks, timeout=8)
            for task in pending:
                task.cancel()
        records = []
        for task in done:
            try:
                record = task.result()
                if record is not None:
                    records.append(record)
            except (httpx.HTTPError, ValueError, ET.ParseError, TypeError, OverflowError):
                partial = True
        return {"records": records, "partial": partial or bool(pending), "published": _iso(published), "checked": _iso(now)}


def query_alerts(latitude, longitude, country):
    now = timezone.now()
    base = {
        "ubicacion": {"latitud": latitude, "longitud": longitude, "pais": country},
        "estado": "fuera_cobertura" if country != "AR" else "no_disponible",
        "alertas": [],
        "fuente": {"nombre": "Servicio Meteorológico Nacional", "url": SOURCE, "consultado_en_utc": _iso(now), "publicado_en_utc": None},
    }
    if country != "AR":
        return base
    try:
        catalog = cache.get(CACHE_KEY)
        if catalog is None:
            catalog = _load_catalog(now)
            cache.set(CACHE_KEY, catalog, 30 if catalog['partial'] else 180)
        if now - _utc(catalog['published']) > timedelta(hours=24):
            return base
        base['fuente'].update(consultado_en_utc=catalog['checked'], publicado_en_utc=catalog['published'])
        suppressed = {ref for record in catalog['records'] for ref in record['references']}
        notices, seen = [], set()
        for record in sorted(catalog['records'], key=lambda row: row['sent'], reverse=True):
            if record['cancel'] or record['id'] in suppressed or record['id'] in seen:
                continue
            seen.add(record['id'])
            for notice in record['notices']:
                if _utc(notice['fin_utc']) <= now or _utc(notice['emitido_en_utc']) > now + timedelta(minutes=15):
                    continue
                if any(_inside(latitude, longitude, shape) for shape in notice['shapes']):
                    notices.append({key: value for key, value in notice.items() if key != 'shapes'})
        rank = {"Extreme": 0, "Severe": 1, "Moderate": 2, "Minor": 3, "Unknown": 4}
        base.update(estado="parcial" if catalog['partial'] else "disponible", alertas=sorted(notices, key=lambda row: (rank[row['severidad']], row['inicio_utc'])))
    except (httpx.HTTPError, ValueError, ET.ParseError, TypeError, OverflowError):
        pass
    return base
