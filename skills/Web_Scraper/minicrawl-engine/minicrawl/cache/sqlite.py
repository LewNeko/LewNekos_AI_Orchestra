from __future__ import annotations

import json
import sqlite3
import threading
import time

from ..models import WebDocument

SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    key TEXT PRIMARY KEY, url TEXT, final_url TEXT, fetched_ts REAL,
    status_code INTEGER, content_hash TEXT, doc TEXT
);
CREATE INDEX IF NOT EXISTS pages_url ON pages(url);
"""


class SqliteCache:
    def __init__(self, path: str):
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.executescript(SCHEMA)
        self._lock = threading.Lock()

    def get(self, key: str, max_age: float) -> WebDocument | None:
        with self._lock:
            row = self._db.execute("SELECT fetched_ts, doc FROM pages WHERE key=?", (key,)).fetchone()
        if not row or time.time() - row[0] > max_age:
            return None
        return WebDocument.from_dict(json.loads(row[1]))

    def put(self, key: str, doc: WebDocument) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO pages VALUES (?,?,?,?,?,?,?)",
                (key, doc.url, doc.final_url, time.time(), doc.status_code, doc.content_hash,
                 json.dumps(doc.to_dict())))
            self._db.commit()

    def history(self, url: str) -> list:
        """(fetched_ts, content_hash) rows for a URL: lets an auditor see whether a page changed."""
        with self._lock:
            return self._db.execute("SELECT fetched_ts, content_hash FROM pages WHERE url=? ORDER BY fetched_ts",
                                    (url,)).fetchall()

    def close(self) -> None:
        self._db.close()
