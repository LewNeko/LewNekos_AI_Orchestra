from __future__ import annotations

import httpx

from ..engine import SearchResult


class SearxngProvider:
    name = "searxng"

    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")

    async def search(self, query: str, limit: int) -> list:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(f"{self.base}/search", params={"q": query, "format": "json"})
            r.raise_for_status()
        return [SearchResult(x.get("title", ""), x["url"], x.get("content", ""), self.name)
                for x in r.json().get("results", [])[:limit] if x.get("url")]
