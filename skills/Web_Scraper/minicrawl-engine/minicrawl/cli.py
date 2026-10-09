from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict

from .client import MiniCrawl
from .config import CrawlOptions, EngineConfig, ScrapeOptions


def _dump(o):
    print(json.dumps(o, indent=2, ensure_ascii=False, default=str))


async def _run(a) -> None:
    cfg = EngineConfig(cache_path=a.cache)
    async with MiniCrawl(cfg) as mc:
        if a.events:
            mc.bus.subscribe(lambda e: print(json.dumps(e), file=sys.stderr))
        if a.cmd == "scrape":
            doc = await mc.scrape(a.url, ScrapeOptions(render=a.render, only_main_content=not a.full,
                                                       screenshot=a.screenshot, max_age=a.max_age))
            _dump(doc.to_dict()) if a.json else print(doc.to_markdown())
        elif a.cmd == "crawl":
            res = await mc.crawl(a.url, CrawlOptions(limit=a.limit, max_depth=a.depth, include_paths=a.include or [],
                                                     exclude_paths=a.exclude or [], respect_robots=not a.ignore_robots,
                                                     use_sitemap=a.sitemap, keywords=a.keyword or [],
                                                     scrape=ScrapeOptions(render=a.render, max_age=a.max_age)))
            _dump(res.to_dict())
        elif a.cmd == "map":
            print("\n".join(await mc.map(a.url, a.search)))
        elif a.cmd == "search":
            _dump([asdict(r) for r in await mc.search(a.query, a.limit)])
        elif a.cmd == "research":
            _dump(asdict(await mc.research(a.question, a.url or None, top_k=a.top_k)))


def main() -> None:
    p = argparse.ArgumentParser(prog="minicrawl", description="Self-hosted web evidence engine")
    p.add_argument("--cache", help="sqlite cache path")
    p.add_argument("--events", action="store_true", help="stream runtime events (JSONL) to stderr")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scrape"); s.add_argument("url"); s.add_argument("--render", default="auto", choices=["auto", "always", "never"])
    s.add_argument("--full", action="store_true"); s.add_argument("--json", action="store_true")
    s.add_argument("--screenshot", action="store_true"); s.add_argument("--max-age", type=float)
    c = sub.add_parser("crawl"); c.add_argument("url"); c.add_argument("--limit", type=int, default=10)
    c.add_argument("--depth", type=int, default=2); c.add_argument("--include", action="append"); c.add_argument("--exclude", action="append")
    c.add_argument("--keyword", action="append"); c.add_argument("--sitemap", action="store_true")
    c.add_argument("--ignore-robots", action="store_true"); c.add_argument("--render", default="auto", choices=["auto", "always", "never"])
    c.add_argument("--max-age", type=float)
    m = sub.add_parser("map"); m.add_argument("url"); m.add_argument("--search")
    q = sub.add_parser("search"); q.add_argument("query"); q.add_argument("--limit", type=int, default=5)
    r = sub.add_parser("research"); r.add_argument("question"); r.add_argument("--url", action="append", help="skip search; use these URLs")
    r.add_argument("--top-k", type=int, default=8)
    sv = sub.add_parser("serve"); sv.add_argument("--host", default="0.0.0.0"); sv.add_argument("--port", type=int, default=3002)
    a = p.parse_args()
    if a.cmd == "serve":
        import uvicorn
        from .api import create_app
        uvicorn.run(create_app(), host=a.host, port=a.port)
    else:
        asyncio.run(_run(a))
