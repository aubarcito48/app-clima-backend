"""Atomic, bounded advice cache and daily attempt budget, shared via SQLite.

Only hashes, validated advice and counters are stored. Never credentials/prompts.
The configured directory MUST be persistent in production and shared by workers.
"""

from contextlib import closing
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import time

from django.conf import settings


def cache_key(messages, language, director):
    payload = [messages, language, director, settings.GROQ_MODEL,
               settings.GROQ_MAX_COMPLETION_TOKENS, 'advice-v1']
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False).encode()).hexdigest()


class AdviceBudget:
    def __init__(self, path):
        self.path = str(path)

    def connect(self):
        if not self.path:
            raise OSError('Missing persistent budget path')
        path = Path(self.path)
        if not path.is_absolute():
            raise OSError('Budget path must be absolute')
        if path.is_dir():
            raise OSError('Budget path must be a file')
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=1, isolation_level=None)
        try:
            db.execute('CREATE TABLE IF NOT EXISTS budget '
                       '(id INTEGER PRIMARY KEY CHECK (id=1), day TEXT NOT NULL, used INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS advice '
                       '(key TEXT PRIMARY KEY, expires REAL NOT NULL, value TEXT)')
        except BaseException:
            db.close()
            raise
        return db

    def acquire(self, key, *, now=None):
        """Return (cached value, reservation). Pending/failed calls never retry immediately."""
        now = time.time() if now is None else now
        day = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
        with closing(self.connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                db.execute('DELETE FROM advice WHERE expires <= ?', (now,))
                row = db.execute('SELECT value FROM advice WHERE key=?', (key,)).fetchone()
                if row:
                    db.commit()
                    return (json.loads(row[0]) if row[0] else None), False
                row = db.execute('SELECT day, used FROM budget WHERE id=1').fetchone()
                if row and row[0] > day:
                    db.commit()  # Clock rollback must not grant another allowance.
                    return None, False
                used = row[1] if row and row[0] == day else 0
                count = db.execute('SELECT count(*) FROM advice').fetchone()[0]
                if used >= settings.GROQ_DAILY_REQUEST_LIMIT or count >= settings.GROQ_CACHE_MAX_ENTRIES:
                    db.commit()
                    return None, False
                db.execute('INSERT OR REPLACE INTO budget VALUES (1, ?, ?)', (day, used + 1))
                # A crash still consumes its allowance; the pending key expires.
                db.execute('INSERT INTO advice VALUES (?, ?, NULL)', (key, now + 120))
                db.commit()
                return None, True
            except BaseException:
                db.rollback()
                raise

    def finish(self, key, result):
        valid = result.get('estado') == 'disponible'
        ttl = settings.GROQ_CACHE_TTL_SECONDS if valid else 30
        value = json.dumps(deepcopy(result), ensure_ascii=False) if valid else None
        with closing(self.connect()) as db:
            db.execute('UPDATE advice SET expires=?, value=? WHERE key=?',
                       (time.time() + ttl, value, key))


def guarded_advice(messages, language, director, generate):
    unavailable = {'estado': 'no_disponible', 'texto': None}
    budget = AdviceBudget(settings.GROQ_BUDGET_PATH)
    try:
        key = cache_key(messages, language, director)
        cached, reserved = budget.acquire(key)
        if cached is not None:
            return cached
        if not reserved:
            return unavailable
    except (OSError, sqlite3.Error, ValueError, TypeError):
        return unavailable  # Fail closed: never spend without an atomic reservation.
    result = generate()
    try:
        budget.finish(key, result)
    except (OSError, sqlite3.Error):
        pass  # The durable attempt reservation remains consumed.
    return result
