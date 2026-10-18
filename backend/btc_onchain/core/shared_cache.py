"""Single-process shared historical cache, persisted beside evaluation data.

Keys include model version, range and canonical end hash. A reorg therefore
cannot reuse an obsolete range. Values are bounded, expendable derived data.
"""
import asyncio
import json
import os
import sqlite3
from pathlib import Path

class SharedCache:
    def __init__(self, path=None):
        self.path = Path(path or os.environ.get('MODEL_CACHE_DB', str(Path(os.environ.get('EXT_PRICE_DB', 'external_prices.sqlite')).with_name('model_cache.sqlite'))))
        self.lock = asyncio.Lock()
        self.computations = 0
        self.hits = 0
        self._db = None

    def db(self):
        if self._db is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(self.path)
            self._db.execute('CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT NOT NULL, touched REAL NOT NULL)')
        return self._db

    def get(self, key):
        row = self.db().execute('SELECT value FROM cache WHERE key=?', (key,)).fetchone()
        if row:
            self.hits += 1
            return json.loads(row[0])
        return None

    def put(self, key, value, limit=320):
        import time
        db = self.db()
        with db:
            db.execute('INSERT OR REPLACE INTO cache VALUES (?, ?, ?)', (key, json.dumps(value, default=lambda item: item.model_dump()), time.time()))
            db.execute('DELETE FROM cache WHERE key NOT IN (SELECT key FROM cache ORDER BY touched DESC LIMIT ?)', (limit,))

    async def obtain(self, key, factory):
        # Ready views remain available while a different cold job runs.
        cached = self.get(key)
        if cached is not None:
            return cached
        # AppState shields this operation from browser cancellation.
        async with self.lock:
            cached = self.get(key)
            if cached is not None:
                return cached
            value = await factory()
            self.put(key, value)
            self.computations += 1
            return value
