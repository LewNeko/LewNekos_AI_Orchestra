# Web_Scraper Skill

> **Status: two artefacts live here.**
> 1. `minicrawl.py` - a small placeholder (empty file, kept for history).
> 2. `minicrawl-engine/` - a self-hostedd web **acquisition** engine (not a Firecrawl clone) whose center of gravity is *trustworth evidence*. This is the real implementation.

> The `Plans_for_improvement.md` file is a design memo that the `minicrawl-engine` code was built to satisfy.

## Overiew
The web scraper is the intended ingestion source for Html.web documents. It is positioned upstream of `The_Chunker`: scrape &rightarrow; clean &rightarrow; structured `WebDocument` &rightarrow; chunk &rightarrow; `The_Reader`. Its design principle (per `minicrawl-engine/README.md`):

> The crawler never knows how content was obtained; the extractor interprets evidence but never invents citations.

## Entry points
- **Package**: `minicrawl-engine/minicrawl/` (see `minicrawl-engine/pyproject.toml`).
- **Install**: `pip install -e ".[all]"` inside `minicrawl-engine/`; optional `playwright install chromium` for JS rendering.
- **CLI**: `python -m minicrawl scrape | crawl | map | search | research | serve` - full flags in the engine's `README.md`.
- **API**: `MiniCrawl` class (`minicrawl-engine/minicrawl/client.py`) with async `scrape`, `crawl`, `research`, plus a `bus` for runtime events.

## What is actually implemented (verified from the engine's README + folder layout)
| Capability | Where |
|------------|-------|
| Fetch strategy + auto escalation (cheap HTTP first, Chromium only if needed) | `fetch/strategy.py`, `fetch/browser.py` |
| Typed errors, exponential backoff + jitter, Retry-After | `errors.py`, `fetch/http.py` |
| Per-domain concurrency + delay, robots Crawl-delay | `fetch/ratelimit.py`, `crawl/robots.py` |
| Priority frontier, URL canonicalisation / junk rejection | `crawl/frontier.py`, `crawl/urls.py` |
| Document model with provenance (selector computed on the *original* DOM) | `models.py`, `parse/html.py` |
|Scored main-context extraction, structured tables | `parse/html.py`, `parse/tables.py` |
|PDF / JSON / text pipelines | `parse/` |
| SQLite cache + per-URL content-hash history | `cache/sqlite.py` |
| Search providers (SearXNG, Brave) | `search/` |
| Schema extraction with checked citation | `extraction/` |
| Evidence mode (BM25 over blocks, `verify()`) | `evidence/`, `MiniCrawl.research` |
| Runtime event (`fetch.*`, `crawl.*`, `cache.*`) | `runtime/events.py` |

## Honest limits (from the engine's README)
- `relevance` on evidence is **lexical (BM25, 0..1)** - not a truth probability.
- Block selectors are structural paths against the HTML as fetched (or the rendered DOM for browser fetches).
- No CAPTCHA solving, proxy rotation, or auth flows. Bot-walls are detected and escalated to a browser, not defeated.
- Crawl jobs are in-memory; the SQLite cache is the only persistence.

## Integration with the Orchestra
- **Downstream**: `WebDocument` &rightarrow; (future) `The_Chunker` &rightarrow; `The_Reader`.
- **Evidence contract**: `MiniCrawl.research(question, urls=...)` returns a `Report` with `evidence` entries that must pass `verify(e,pages)` - every citation is checkable against the parsed page. That is the same "deterministic check" philosophy as `The_Reader`.
- **Not yet wired**: there is no `The_Web_Scraper` package at the repo root and no skill-registered integration; the engine lives under `skills/Web_Scraper/minicrawl-engine/`.

## Related files
- `minicrawl-engine/README.md` - authoritative description, install, and usage.
- `Plans_for_improvement.md` - the design memo that the engine implements.
- `minicrawl.py` - empty placeholder; no functional code.
