"""Shared normalization and fixed path for the read-only geographical catalog."""

from pathlib import Path
import unicodedata

CATALOG_PATH = Path(__file__).resolve().parents[3] / 'data' / 'places.sqlite'


def normalize_name(value):
    folded = unicodedata.normalize('NFKD', value.casefold())
    return ' '.join(''.join(
        char if char.isalnum() else ' '
        for char in folded if not unicodedata.combining(char)
    ).split())


def catalog_uri():
    # URI ro prevents accidental creation/writes; immutable avoids journals/locks.
    return CATALOG_PATH.as_uri() + '?mode=ro&immutable=1'
