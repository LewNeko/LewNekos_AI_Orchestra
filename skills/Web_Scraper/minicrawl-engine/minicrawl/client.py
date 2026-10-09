from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field

from .cache.sqlite import SqliteCache
from .config import CrawlOptions, EngineConfig, ScrapeOptions, cache_key
from .crawl.crawler import run_crawl
from .crawl.robots import RobotsCache
from .crawl.sitemap import sitemap_urls
from .crawl.urls import canonicalize, is_junk, same_site
from .evidence.citations import rank_blocks
from .extraction.extractor import extract as _extract
from .fetch.browser import BrowserFetcher
from .fetch.http import HttpFetcher
from .fetch.ratelimit import DomainLimiter
from .fetch.strategy import Fetcher
from .models import CrawlResult, WebDocument
from .parse import parse_response
from .runtime.events import EventBus
from .search.engine import SearchEngine


@dataclass
class ResearchReport:
    question: str
    evidence: list = field(default_factory=list)       # list[Evidence], every item traceable to a page
    sources: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    answer: str | None = None                          # only if an llm was supplied
    cited: list = field(default_factory=list)          # evidence ids the answer cites (validated)
    invalid_citations: list = field(default_factory=list)


class MiniCrawl:
    """Self-hosted web evidence engine. Use as `async with MiniCrawl() as mc:`."""

    def __init__(self, config: EngineConfig | None = None, bus: EventBus | None = None, search: SearchEngine | None = None,
                 browser=None):
        self.cfg = config or EngineConfig()
        self.bus = bus or EventBus()
        self.limiter = DomainLimiter(self.cfg.per_domain_concurrency, self.cfg.per_domain_delay, self.cfg.domain_overrides)
        self.http = HttpFetcher(self.cfg, self.limiter, self.bus)
        self.browser = browser or BrowserFetcher(self.cfg, self.limiter, self.bus)
        self.fetcher = Fetcher(self.http, self.browser, self.bus)
        self.robots = RobotsCache(self.http.client, self.cfg.user_agent)
        self.cache = SqliteCache(self.cfg.cache_path) if self.cfg.cache_path else None
        self.search_engine = search or SearchEngine()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.aclose()

    async def aclose(self):
        await self.http.aclose()
        await self.browser.aclose()
        if self.cache:
            self.cache.close()

    # ---- scrape --------------------------------------------------------------
    async def scrape(self, url: str, opts: ScrapeOptions | None = None, depth: int | None = None) -> WebDocument:
        opts = opts or ScrapeOptions()
        key = cache_key(url, opts)
        if self.cache and opts.max_age is not None:
            hit = self.cache.get(key, opts.max_age)
            if hit:
                hit.from_cache, hit.depth = True, depth
                self.bus.emit("cache.hit", url=url)
                return hit
        self.bus.emit("fetch.started", url=url)
        try:
            raw = await self.fetcher.fetch(url, opts)
        except Exception as e:
            self.bus.emit("fetch.failed", url=url, error=type(e).__name__, message=str(e))
            raise
        self.bus.emit("fetch.completed", url=url, status=raw.status, method=raw.method, duration_ms=raw.duration_ms)
        doc = await asyncio.to_thread(parse_response, raw, opts, depth)      # parsing is CPU-bound
        self.bus.emit("content.extracted", url=url, blocks=len(doc.blocks), tables=len(doc.tables), words=doc.word_count)
        if self.cache:
            self.cache.put(key, doc)
            self.bus.emit("page.cached", url=url, content_hash=doc.content_hash)
        return doc

    # ---- crawl / map ---------------------------------------------------------
    async def crawl(self, url: str, opts: CrawlOptions | None = None, result: CrawlResult | None = None) -> CrawlResult:
        result = result or CrawlResult()
        await run_crawl(self, url, opts or CrawlOptions(), result)
        return result

    async def map(self, url: str, search: str | None = None, limit: int = 5000) -> list:
        urls = await sitemap_urls(self.http.client, url, limit)
        try:
            urls += (await self.scrape(url, ScrapeOptions(render="never", only_main_content=False))).links
        except Exception:
            pass
        seen, out = set(), []
        for u in map(canonicalize, urls):
            if u not in seen and same_site(u, url) and not is_junk(u):
                seen.add(u)
                out.append(u)
        if search:
            out = [u for u in out if search.lower() in u.lower()]
        return out[:limit]

    # ---- search / extract / research ----------------------------------------
    async def search(self, query: str, limit: int = 5, scrape: bool = False, opts: ScrapeOptions | None = None):
        results = await self.search_engine.search(query, limit)
        self.bus.emit("search.completed", query=query, results=len(results))
        if not scrape:
            return results
        docs = await asyncio.gather(*[self.scrape(r.url, opts) for r in results], return_exceptions=True)
        return [(r, d) for r, d in zip(results, docs) if isinstance(d, WebDocument)]

    async def extract(self, url_or_doc, schema: dict, llm, prompt: str | None = None):
        doc = url_or_doc if isinstance(url_or_doc, WebDocument) else await self.scrape(url_or_doc)
        return await _extract(doc, schema, llm, prompt)

    async def research(self, question: str, urls: list | None = None, search_limit: int = 5, top_k: int = 8,
                       llm=None, opts: ScrapeOptions | None = None) -> ResearchReport:
        """Find, fetch, and rank evidence. Citations come from parsed blocks, never from a model.
        With `llm`, also drafts an answer that may only cite evidence ids (validated afterwards)."""
        report = ResearchReport(question=question)
        if not urls:
            urls = [r.url for r in await self.search_engine.search(question, search_limit)]
        res = await asyncio.gather(*[self.scrape(u, opts) for u in urls], return_exceptions=True)
        docs = []
        for u, r in zip(urls, res):
            if isinstance(r, WebDocument):
                docs.append(r)
                report.sources.append(r.final_url)
            else:
                report.errors.append({"url": u, "kind": type(r).__name__, "message": str(r)})
        report.evidence = rank_blocks(question, docs, top_k)
        self.bus.emit("research.completed", question=question, sources=len(docs), evidence=len(report.evidence))
        if llm and report.evidence:
            ev_text = "\n".join(f"[{e.id}] ({e.source_url}) {e.text}" for e in report.evidence)
            report.answer = await llm(
                f"Question: {question}\n\nAnswer using ONLY the evidence below. Cite evidence ids like [e1] after "
                f"each claim. If the evidence is insufficient, say so.\n\n{ev_text}")
            ids = {e.id for e in report.evidence}
            found = re.findall(r"\[(e\d+)\]", report.answer)
            report.cited = sorted({i for i in found if i in ids})
            report.invalid_citations = sorted({i for i in found if i not in ids})
        return report
