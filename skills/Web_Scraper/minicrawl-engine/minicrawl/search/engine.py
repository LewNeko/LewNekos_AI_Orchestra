from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from ..errors import SearchUnavailable


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    provider: str


class SearchProvider(Protocol):
    name: str

    async def search(self, query: str, limit: int) -> list: ...


class SearchEngine:
    def __init__(self, providers: list | None = None):
        self.providers = providers if providers is not None else default_providers()

    async def search(self, query: str, limit: int = 5) -> list:
        if not self.providers:
            raise SearchUnavailable("no search provider configured: set SEARXNG_URL or BRAVE_API_KEY, "
                                    "or pass providers=[...] to MiniCrawl")
        errors = []
        for p in self.providers:          # first provider that answers wins
            try:
                results = await p.search(query, limit)
                if results:
                    return results[:limit]
            except Exception as e:
                errors.append(f"{p.name}: {e}")
        if errors:
            raise SearchUnavailable("; ".join(errors))
        return []


def default_providers() -> list:
    from .providers.brave import BraveProvider
    from .providers.searxng import SearxngProvider
    out = []
    if os.getenv("SEARXNG_URL"):
        out.append(SearxngProvider(os.environ["SEARXNG_URL"]))
    if os.getenv("BRAVE_API_KEY"):
        out.append(BraveProvider(os.environ["BRAVE_API_KEY"]))
    return out
