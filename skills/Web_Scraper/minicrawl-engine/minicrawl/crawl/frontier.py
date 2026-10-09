"""Priority frontier: highest-priority URL first, de-duplicated, with clean termination."""
from __future__ import annotations

import asyncio
import heapq
import itertools


class Frontier:
    def __init__(self):
        self._heap: list = []
        self._seen: set = set()
        self._cv = asyncio.Condition()
        self._counter = itertools.count()
        self._in_flight = 0
        self._closed = False

    async def add(self, url: str, depth: int, priority: float) -> bool:
        async with self._cv:
            if url in self._seen or self._closed:
                return False
            self._seen.add(url)
            heapq.heappush(self._heap, (-priority, next(self._counter), url, depth))
            self._cv.notify()
            return True

    async def get(self):
        """Next (url, depth), or None once the frontier is exhausted/closed. Call task_done() afterwards."""
        async with self._cv:
            while not self._heap:
                if self._in_flight == 0 or self._closed:
                    self._cv.notify_all()
                    return None
                await self._cv.wait()
            if self._closed:
                return None
            _, _, url, depth = heapq.heappop(self._heap)
            self._in_flight += 1
            return url, depth

    async def task_done(self):
        async with self._cv:
            self._in_flight -= 1
            self._cv.notify_all()

    async def close(self):
        async with self._cv:
            self._closed = True
            self._cv.notify_all()
