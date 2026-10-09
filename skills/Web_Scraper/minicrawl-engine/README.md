# minicrawl: a self-hosted web evidence engine

Not a Firecrawl clone: a web *acquisition* engine whose centre of gravity is **trustworthy evidence**.
The crawler never knows how content was obtained; the extractor interprets evidence but never invents citations.

```
Fetcher (cheap HTTP first, Chromium only if needed) -> content detector (HTML/PDF/JSON/text)
  -> scored main-content extraction -> WebDocument (blocks + tables + provenance)
  -> SQLite cache -> scrape / crawl / map / search / extract / research        (events emitted throughout)
```

## Install
```
pip install -e ".[all]"          # or pick extras: api, pdf, browser
playwright install chromium      # only for JS rendering / screenshots / interaction
```

## Use
```python
import asyncio
from minicrawl import MiniCrawl, EngineConfig, ScrapeOptions, CrawlOptions, verify

async def main():
    async with MiniCrawl(EngineConfig(cache_path="cache.sqlite")) as mc:
        mc.bus.subscribe(print, "fetch.")                       # runtime events
        doc = await mc.scrape("https://example.com", ScrapeOptions(max_age=86400))
        doc.to_markdown(); doc.to_text(); doc.tables; doc.blocks   # blocks carry url + CSS selector + heading path
        res = await mc.crawl("https://example.com", CrawlOptions(limit=20, keywords=["pricing"]))
        rep = await mc.research("Who founded Example?", urls=[p.final_url for p in res.pages])
        assert all(verify(e, res.pages) for e in rep.evidence)  # every citation checked against the parsed page

asyncio.run(main())
```
CLI: `python -m minicrawl scrape URL --render auto|always|never --max-age 3600 --events`,
`crawl`, `map`, `search`, `research "question" --url ...`, `serve --port 3002`.

## What maps to the plan
| Plan item | Where |
|---|---|
| Fetch strategy + auto escalation, browser actions/screenshots | `fetch/strategy.py`, `fetch/browser.py` |
| Document model, provenance (selector computed on the *original* DOM) | `models.py`, `parse/html.py` |
| Scored main-content extraction, structured tables | `parse/html.py`, `parse/tables.py` |
| PDF / JSON / text pipelines | `parse/` |
| SQLite cache + per-URL content-hash history | `cache/sqlite.py` |
| Priority frontier, URL canonicalisation/junk rejection | `crawl/frontier.py`, `crawl/urls.py` |
| Typed errors, exponential backoff + jitter, Retry-After | `errors.py`, `fetch/http.py` |
| Per-domain concurrency + delay, robots Crawl-delay | `fetch/ratelimit.py`, `crawl/robots.py` |
| Events (`fetch.*`, `crawl.*`, `cache.*`, ...) | `runtime/events.py` |
| Search providers (SearXNG, Brave) | `search/` |
| Schema extraction with checked citations | `extraction/` |
| Evidence mode (BM25 over blocks, `verify()`) | `evidence/`, `MiniCrawl.research` |

## Honest limits
- `relevance` on evidence is lexical (BM25, 0..1). It is **not** a truth probability.
- Block selectors are structural paths (`#id` or `:nth-of-type`) against the HTML as fetched; for browser fetches, against the rendered DOM.
- No CAPTCHA solving, proxy rotation or auth flows. Bot-walls are detected and escalate to a browser, not defeated.
- Crawl jobs are in-memory; the cache is the only persistence.
