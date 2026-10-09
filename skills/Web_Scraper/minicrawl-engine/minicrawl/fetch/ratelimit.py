"""Per-domain politeness: bounded concurrency AND a minimum gap between request starts."""
from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from urllib.parse import urlparse


class _Host:
    def __init__(self, concurrency: int, delay: float):
        self.sem = asyncio.Semaphore(concurrency)
        self.lock = asyncio.Lock()
        self.delay = delay
        self.next_at = 0.0


class DomainLimiter:
    def __init__(self, concurrency: int = 2, delay: float = 0.5, overrides: dict | None = None):
        self.concurrency, self.delay = concurrency, delay
        self.overrides = overrides or {}
        self._hosts: dict[str, _Host] = {}

    def _host(self, url: str) -> _Host:
        host = urlparse(url).netloc.lower()
        if host not in self._hosts:
            o = self.overrides.get(host, {})
            self._hosts[host] = _Host(o.get("concurrency", self.concurrency), o.get("delay", self.delay))
        return self._hosts[host]

    def set_delay(self, url: str, delay: float) -> None:
        """Raise (never lower) a host's delay, e.g. from robots.txt Crawl-delay."""
        h = self._host(url)
        h.delay = max(h.delay, delay)

    @asynccontextmanager
    async def slot(self, url: str):
        h = self._host(url)
        async with h.sem:
            async with h.lock:
                wait = h.next_at - time.monotonic()
                if wait > 0:
                    await asyncio.sleep(wait)
                h.next_at = time.monotonic() + h.delay
            yield
