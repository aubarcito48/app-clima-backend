"""Build the static place catalog from pinned GeoNames downloads, never user data.

Usage: python scripts/build_place_catalog.py --download
No download, database generation or update happens during application startup.
"""

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from api.services.places.place_catalog import CATALOG_PATH
from api.services.places.place_catalog import normalize_name

SOURCES = {
    'cities1000.zip': '46a35f52226f34dd56b64d57b4e9bb380a8ad06605354f8095ea9cdc561aba2c',
    'admin1CodesASCII.txt': '2e4867f5397acb056ea26377601b57af37cb4c81399770225018e9e439e91ad3',
}
BASE_URL = 'https://download.geonames.org/export/dump/'


def build(source_dir, output):
    blobs = {}
    for name, expected in SOURCES.items():
        blob = (source_dir / name).read_bytes()
        if hashlib.sha256(blob).hexdigest() != expected:
            raise ValueError(f'Source checksum mismatch: {name}. Review a new snapshot before updating hashes.')
        blobs[name] = blob
    regions = {}
    for line in blobs['admin1CodesASCII.txt'].decode('utf-8').splitlines():
        code, name, *_ = line.split('\t')
        regions[code] = name
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.building')
    if temporary.exists():
        raise ValueError(f'A previous temporary build exists: {temporary}')
    with sqlite3.connect(temporary) as db:
        db.executescript('''
            PRAGMA page_size=4096;
            CREATE TABLE cities (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, name_key TEXT NOT NULL, country TEXT NOT NULL,
                region TEXT, region_key TEXT NOT NULL,
                latitude REAL NOT NULL, longitude REAL NOT NULL, population INTEGER NOT NULL
            );
            CREATE TABLE names (
                name TEXT NOT NULL, city_id INTEGER NOT NULL,
                PRIMARY KEY (name, city_id)
            ) WITHOUT ROWID;
            PRAGMA user_version=1;
        ''')
        count = 0
        with zipfile.ZipFile(io.BytesIO(blobs['cities1000.zip'])) as archive:
            with archive.open('cities1000.txt') as stream:
                for line in io.TextIOWrapper(stream, encoding='utf-8'):
                    row = line.rstrip('\n').split('\t')
                    name, country = row[1], row[8]
                    region = regions.get(country + '.' + row[10])
                    lat, lon = float(row[4]), float(row[5])
                    if (not 1 <= len(name) <= 100 or not re.fullmatch('[A-Z]{2}', country)
                            or (region and len(region) > 100) or not -90 <= lat <= 90 or not -180 <= lon <= 180):
                        continue
                    city_id = int(row[0])
                    db.execute('INSERT INTO cities VALUES (?,?,?,?,?,?,?,?,?)', (
                        city_id, name, normalize_name(name), country, region, normalize_name(region or ''), lat, lon, int(row[14]),
                    ))
                    # Do not turn airport-like abbreviations (e.g. SAN) into city names.
                    aliases = [alias for alias in row[3].split(',') if not re.fullmatch('[A-Z]{3}', alias)]
                    names = {normalize_name(item) for item in [name, row[2], *aliases]}
                    db.executemany('INSERT INTO names VALUES (?,?)', (
                        (alias, city_id) for alias in sorted(names) if 1 <= len(alias) <= 100
                    ))
                    count += 1
        db.execute('ANALYZE')
        alias_count = db.execute('SELECT count(*) FROM names').fetchone()[0]
    # Close before replacing on Windows.
    db.close()
    temporary.replace(output)
    manifest = {
        'schema': 1, 'snapshot_date': '2026-11-16', 'cities': count, 'names': alias_count,
        'catalog_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        'sources': [{'url': BASE_URL + name, 'sha256': digest} for name, digest in SOURCES.items()],
        'license': 'CC BY 4.0', 'attribution': 'GeoNames · https://www.geonames.org/',
        'transformations': 'Selected fields, normalized and deduplicated search aliases, indexed read-only catalog.',
    }
    output.with_suffix('.manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'cities': count, 'names': alias_count, 'bytes': output.stat().st_size}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=ROOT / 'tmp' / 'place-catalog')
    parser.add_argument('--output', type=Path, default=CATALOG_PATH)
    parser.add_argument('--download', action='store_true')
    args = parser.parse_args()
    if args.download:
        args.source_dir.mkdir(parents=True, exist_ok=True)
        for name in SOURCES:
            target = args.source_dir / name
            if not target.exists():
                with urllib.request.urlopen(BASE_URL + name, timeout=45) as response:
                    blob = response.read(64 * 1024 * 1024 + 1)
                if len(blob) > 64 * 1024 * 1024:
                    raise ValueError('Source download too large')
                target.write_bytes(blob)
    build(args.source_dir, args.output)
