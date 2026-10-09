from __future__ import annotations

import asyncio
import random
import time

import httpx

from ..errors import (BlockedError, FetchError, FetchTimeout, HTTPStatusError, RateLimitError, ServerError)
from .base import RawResponse


def backoff(attempt: int, base: float, cap: float) -> float:
    delay = min(cap, base * (2 ** attempt))
    return delay + random.uniform(0, delay * 0.25)       # jitter


class HttpFetcher:
    def __init__(self, cfg, limiter, bus):
        self.cfg, self.limiter, self.bus = cfg, limiter, bus
        self.client = httpx.AsyncClient(headers={"User-Agent": cfg.user_agent}, timeout=cfg.timeout,
                                        follow_redirects=True)

    async def aclose(self):
        await self.client.aclose()

    def _classify(self, r: httpx.Response, url: str) -> None:
        s = r.status_code
        if s in (429, 503):
            ra = r.headers.get("retry-after", "")
            raise RateLimitError(f"HTTP {s}", url, s, float(ra) if ra.replace(".", "", 1).isdigit() else None)
        if s >= 500:
            raise ServerError(f"HTTP {s}", url, s)
        if s in (401, 403, 451):
            raise BlockedError(f"HTTP {s}", url, s, response=self._raw(r, url, 0))
        if s >= 400:
            raise HTTPStatusError(f"HTTP {s}", url, s)

    @staticmethod
    def _raw(r: httpx.Response, url: str, ms: int) -> RawResponse:
        return RawResponse(url=url, final_url=str(r.url), status=r.status_code,
                           content_type=r.headers.get("content-type", ""), body=r.content,
                           method="http", encoding=r.encoding, duration_ms=ms)

    async def fetch(self, url: str, timeout: float | None = None) -> RawResponse:
        last: Exception | None = None
        for attempt in range(self.cfg.max_retries + 1):
            delay = 0.0
            try:
                async with self.limiter.slot(url):
                    t0 = time.monotonic()
                    r = await self.client.get(url, timeout=timeout or self.cfg.timeout)
                    ms = int((time.monotonic() - t0) * 1000)
                if len(r.content) > self.cfg.max_bytes:
                    raise FetchError(f"response larger than {self.cfg.max_bytes} bytes", url, r.status_code)
                self._classify(r, url)
                return self._raw(r, url, ms)
            except RateLimitError as e:
                last, delay = e, e.retry_after if e.retry_after is not None else backoff(attempt, self.cfg.backoff_base, self.cfg.backoff_max)
            except ServerError as e:
                last, delay = e, backoff(attempt, self.cfg.backoff_base, self.cfg.backoff_max)
            except httpx.TimeoutException as e:
                last, delay = FetchTimeout(f"timeout: {e}", url), backoff(attempt, self.cfg.backoff_base, self.cfg.backoff_max)
            except httpx.TransportError as e:
                last, delay = FetchError(f"transport error: {e}", url), backoff(attempt, self.cfg.backoff_base, self.cfg.backoff_max)
            # BlockedError / HTTPStatusError / oversize FetchError propagate immediately (not retryable)
            if attempt < self.cfg.max_retries:
                self.bus.emit("fetch.retry", url=url, attempt=attempt + 1, error=type(last).__name__, delay_s=round(delay, 2))
                await asyncio.sleep(delay)
        assert last is not None
        raise last
