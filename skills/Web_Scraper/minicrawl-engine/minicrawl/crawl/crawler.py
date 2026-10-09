from __future__ import annotations

import re
import time
from urllib.parse import urlparse

from ..errors import FetchError
from ..models import CrawlError
from .frontier import Frontier
from .sitemap import sitemap_urls
from .urls import canonicalize, is_junk, same_site, url_priority


def path_allowed(url: str, include: list, exclude: list) -> bool:
    path = urlparse(url).path or "/"
    if any(re.search(p, path) for p in exclude):
        return False
    return not include or any(re.search(p, path) for p in include)


async def run_crawl(mc, start_url: str, o, result) -> None:
    """Crawl via mc.scrape(): the crawler never knows HOW content was obtained."""
    start = canonicalize(start_url)
    result.start_url, result.status = start, "running"
    result.stats.started_at = time.time()
    mc.bus.emit("crawl.started", url=start, limit=o.limit, max_depth=o.max_depth)
    frontier = Frontier()
    robots = mc.robots if o.respect_robots else None
    if robots:
        delay = await robots.crawl_delay(start)
        if delay:
            mc.limiter.set_delay(start, delay)

    async def accept(link: str, depth: int) -> None:
        c = canonicalize(link)
        if not same_site(c, start, o.allow_subdomains) or is_junk(c) or not path_allowed(c, o.include_paths, o.exclude_paths):
            result.stats.skipped_filter += 1
            return
        if robots and not await robots.can_fetch(c):
            result.stats.skipped_robots += 1
            return
        if await frontier.add(c, depth, url_priority(c, depth, o.keywords)):
            result.stats.discovered += 1

    await frontier.add(start, 0, 1000.0)
    result.stats.discovered = 1
    if o.use_sitemap:
        for u in await sitemap_urls(mc.http.client, start):
            await accept(u, 1)

    claimed = 0

    async def worker():
        nonlocal claimed
        while True:
            item = await frontier.get()
            if item is None:
                return
            url, depth = item
            try:
                if claimed >= o.limit:
                    continue
                claimed += 1
                try:
                    doc = await mc.scrape(url, o.scrape, depth=depth)
                except Exception as e:
                    claimed -= 1
                    result.errors.append(CrawlError(url=url, kind=type(e).__name__, message=str(e),
                                                    retryable=getattr(e, "retryable", False),
                                                    status=getattr(e, "status", None)))
                    mc.bus.emit("fetch.failed", url=url, error=type(e).__name__, message=str(e))
                    continue
                result.pages.append(doc)
                result.stats.cache_hits += doc.from_cache
                if depth < o.max_depth:
                    for link in doc.links:
                        await accept(link, depth + 1)
                if len(result.pages) >= o.limit:
                    await frontier.close()
            finally:
                await frontier.task_done()

    import asyncio
    try:
        await asyncio.gather(*[worker() for _ in range(o.concurrency)])
        result.status = "completed"
    except Exception as e:
        result.status = "failed"
        result.errors.append(CrawlError(url=start, kind=type(e).__name__, message=str(e)))
    finally:
        result.stats.finished_at = time.time()
        mc.bus.emit("crawl.completed", url=start, pages=len(result.pages), errors=len(result.errors),
                    status=result.status)
