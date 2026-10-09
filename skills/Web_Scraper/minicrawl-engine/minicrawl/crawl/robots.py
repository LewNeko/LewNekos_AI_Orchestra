from __future__ import annotations

import asyncio
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser


class RobotsCache:
    def __init__(self, client, user_agent: str):
        self.client, self.ua = client, user_agent
        self._tasks: dict = {}

    async def _load(self, origin: str) -> RobotFileParser:
        rp = RobotFileParser()
        try:
            r = await self.client.get(origin + "/robots.txt")
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except Exception:
            rp.parse([])
        return rp

    async def _get(self, url: str) -> RobotFileParser:
        p = urlparse(url)
        origin = f"{p.scheme}://{p.netloc}"
        if origin not in self._tasks:
            self._tasks[origin] = asyncio.ensure_future(self._load(origin))
        return await self._tasks[origin]

    async def can_fetch(self, url: str) -> bool:
        return (await self._get(url)).can_fetch(self.ua, url)

    async def crawl_delay(self, url: str) -> float | None:
        d = (await self._get(url)).crawl_delay(self.ua)
        return float(d) if d else None
