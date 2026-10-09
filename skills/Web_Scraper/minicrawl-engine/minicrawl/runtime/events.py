"""Structured events so a runtime (Reader, Auditor, orchestrator) can observe acquisition."""
from __future__ import annotations

import time
from collections import deque


class EventBus:
    def __init__(self, history: int = 1000):
        self.history = deque(maxlen=history)
        self._subs = []

    def subscribe(self, handler, prefix: str | None = None):
        """handler(event: dict). Returns an unsubscribe function."""
        entry = (prefix, handler)
        self._subs.append(entry)
        return lambda: self._subs.remove(entry) if entry in self._subs else None

    def emit(self, name: str, **data) -> dict:
        ev = {"event": name, "ts": time.time(), **data}
        self.history.append(ev)
        for prefix, handler in list(self._subs):
            if prefix is None or name.startswith(prefix):
                try:
                    handler(ev)
                except Exception:
                    pass  # observers must never break acquisition
        return ev
