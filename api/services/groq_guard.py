"""Bounded process-local advice cache; no disk or paid storage required."""

from copy import deepcopy
import hashlib
import json
import threading
import time

from django.conf import settings


def cache_key(messages, language, director):
    payload = [messages, language, director, settings.GROQ_MODEL,
               settings.GROQ_MAX_COMPLETION_TOKENS, 'advice-v1']
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False).encode()).hexdigest()


class AdviceCache:
    def __init__(self):
        self.entries = {}
        self.lock = threading.Lock()

    def acquire(self, key, *, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            self.entries = {key: row for key, row in self.entries.items() if row[0] > now}
            row = self.entries.get(key)
            if row:
                return deepcopy(row[1]), None
            if len(self.entries) >= settings.GROQ_CACHE_MAX_ENTRIES:
                return None, None
            token = object()
            self.entries[key] = (now + 120, None, token)
            return None, token

    def finish(self, key, token, result):
        valid = result.get('estado') == 'disponible'
        ttl = settings.GROQ_CACHE_TTL_SECONDS if valid else 30
        with self.lock:
            row = self.entries.get(key)
            # An expired request must never overwrite a newer reservation.
            if row and row[2] is token:
                self.entries[key] = (time.monotonic() + ttl,
                                     deepcopy(result) if valid else None, token)


advice_cache = AdviceCache()


def guarded_advice(messages, language, director, generate):
    key = cache_key(messages, language, director)
    cached, token = advice_cache.acquire(key)
    if cached is not None:
        return cached
    if token is None:
        return {'estado': 'no_disponible', 'texto': None}
    result = generate()
    advice_cache.finish(key, token, result)
    return result
