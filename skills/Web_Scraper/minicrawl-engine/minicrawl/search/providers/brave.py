from __future__ import annotations

import httpx

from ..engine import SearchResult


class BraveProvider:
    name = "brave"

    def __init__(self, api_key: str):
        self.key = api_key

    async def search(self, query: str, limit: int) -> list:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get("https://api.search.brave.com/res/v1/web/search",
                            params={"q": query, "count": limit},
                            headers={"X-Subscription-Token": self.key, "Accept": "application/json"})
            r.raise_for_status()
        return [SearchResult(x.get("title", ""), x["url"], x.get("description", ""), self.name)
                for x in r.json().get("web", {}).get("results", [])[:limit]]
