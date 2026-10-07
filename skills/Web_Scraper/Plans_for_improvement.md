Yes. And after looking at what you have, I **wouldn’t just add more features to `minicrawl.py`**. I’d change the architecture so it becomes a genuinely capable **self-hosted web acquisition engine**, rather than a Firecrawl API clone.

Your current version already has the right skeleton: scrape → clean → markdown, sitemap/map, BFS crawling, robots handling, async concurrency, and Firecrawl-compatible-ish endpoints. 

But compared with current Firecrawl, it is missing the hard parts: JavaScript rendering, browser interaction, PDFs/documents, structured extraction, screenshots, search, batching, caching, and robust failure handling. Firecrawl itself now advertises those capabilities plus an agent layer. ([GitHub][1])

## What I'd build instead

I'd turn this into something like:

```text
                    ┌──────────────────────┐
                    │      Web Engine      │
                    └──────────┬───────────┘
                               │
                 ┌─────────────┴─────────────┐
                 │                           │
           Static Fetch                 Browser Fetch
             httpx                    Playwright/Chromium
                 │                           │
                 └─────────────┬─────────────┘
                               │
                        Content Detector
                               │
             ┌─────────────────┼─────────────────┐
             │                 │                 │
           HTML               PDF              Other
             │                 │                 │
             └─────────────────┼─────────────────┘
                               │
                     Content Extraction
                               │
             ┌─────────────────┼─────────────────┐
             │                 │                 │
        Main content        Links/media       Metadata
             │                 │                 │
             └─────────────────┼─────────────────┘
                               │
                       Normalization
                               │
             ┌─────────────────┼─────────────────┐
             │                 │                 │
          Markdown           HTML            Structured
             │                                 JSON
             └─────────────────┬───────────────┘
                               │
                         Cache / Storage
                               │
                  ┌────────────┴────────────┐
                  │                         │
                Scrape                    Crawl
                  │                         │
                  └────────────┬────────────┘
                               │
                         Agent / Auditor
```

The important part is that **the crawler shouldn't know how content is obtained**.

---

# 1. First: make `scrape()` much smarter

Right now your scraper essentially does:

```python
resp = await client.get(url)
BeautifulSoup(resp.text)
clean_main_content(...)
markdownify(...)
```

That's excellent for static websites.

But a modern scraper needs a **fetch strategy**:

```python
class FetchStrategy(Enum):
    HTTP = "http"
    BROWSER = "browser"
    AUTO = "auto"
```

Then:

```python
async def fetch(url, options):
    if options.render_js:
        return await browser.fetch(url)

    response = await http.fetch(url)

    if looks_like_empty_shell(response):
        return await browser.fetch(url)

    if looks_like_blocked(response):
        return await browser.fetch(url)

    return response
```

So your system tries the **cheap path first**.

That is actually important.

You don't want to launch Chromium for every Wikipedia page.

---

# 2. Add a real browser layer

This is probably the single biggest missing capability.

Use Playwright:

```text
minicrawl/
│
├── fetch/
│   ├── http.py
│   ├── browser.py
│   └── strategy.py
```

`browser.py` would handle:

```python
await page.goto(url)

await page.wait_for_load_state("networkidle")

await page.click(...)
await page.fill(...)
await page.scroll(...)
await page.wait_for_timeout(...)
```

And then:

```python
html = await page.content()
screenshot = await page.screenshot(...)
```

This gives you something your current implementation fundamentally cannot do.

For example:

```bash
minicrawl scrape https://example.com --render
```

or API:

```json
{
  "url": "https://example.com",
  "render": true
}
```

Firecrawl specifically highlights browser interaction such as clicking, scrolling, filling forms, waiting, authentication and screenshots. ([GitHub][2])

---

# 3. Don't blindly render JavaScript

This is where I'd make yours **better architecturally**.

Have an automatic escalation system:

```text
HTTP request
     │
     ▼
Did we get useful content?
     │
   YES ───────► return
     │
     NO
     ▼
Does page appear JS-dependent?
     │
     YES
     ▼
Playwright
     │
     ▼
Did browser produce useful content?
     │
     YES ───────► return
     │
     NO
     ▼
classified failure
```

Detect things like:

```python
def looks_like_js_shell(html: str) -> bool:
    text = visible_text(html)

    return (
        len(text) < 300
        and (
            "enable javascript" in text.lower()
            or "__next" in html
            or "webpack" in html
        )
    )
```

Obviously you'd want a more sophisticated detector eventually.

---

# 4. Build a proper document model

This is a **huge improvement** I'd make for your AI Orchestra project.

Don't let everything become:

```python
dict
```

Create:

```python
@dataclass
class WebDocument:
    url: str
    final_url: str
    status_code: int

    title: str | None
    description: str | None

    markdown: str
    html: str | None

    links: list[str]
    images: list[str]

    content_type: str
    language: str | None

    fetched_at: datetime

    fetch_method: str
    depth: int | None

    word_count: int
    content_hash: str
```

Then:

```python
@dataclass
class CrawlResult:
    pages: list[WebDocument]
    errors: list[CrawlError]
    stats: CrawlStats
```

This becomes incredibly useful later when your **Auditor** starts consuming web evidence.

---

# 5. Add provenance

This is where I'd deliberately diverge from the normal "LLM scraper."

For every piece of extracted information, retain its origin.

For example:

```json
{
  "text": "The company was founded in 2014.",
  "source": {
    "url": "https://example.com/about",
    "selector": "#history p:nth-child(2)",
    "page_title": "About Example",
    "retrieved_at": "2026-10-04T13:00:00Z"
  }
}
```

Even better:

```python
@dataclass
class ContentBlock:
    text: str
    tag: str
    selector: str | None
    source_url: str
    position: int
```

Now your downstream Auditor can say:

> Claim X came from this exact webpage section.

That's **much more valuable for your project** than merely producing clean Markdown.

---

# 6. Make Markdown extraction much better

Your current extraction:

```python
root = soup.find("main") or soup.find("article") ...
```

is a good start. 

I'd turn it into a scoring system.

For every candidate:

```text
<main>
<article>
<div class="content">
<div id="content">
<section>
```

calculate:

```text
+ paragraph density
+ text length
+ heading density
+ link/text ratio
- navigation links
- repeated elements
- advertisements
- forms
- footer
- sidebar
```

Then:

```python
best_candidate = max(candidates, key=content_score)
```

That is much more robust than:

```python
find("main") or find("article")
```

---

# 7. Preserve structure

Don't reduce everything to Markdown immediately.

Internally preserve:

```text
Document
 ├── H1
 ├── paragraph
 ├── H2
 │    ├── paragraph
 │    ├── table
 │    └── list
 ├── H2
 │    └── code block
 └── references
```

Then generate:

```python
document.to_markdown()
document.to_html()
document.to_text()
document.to_json()
```

That gives you multiple representations from one parse.

---

# 8. Tables need first-class treatment

This is a big one.

A web scraper that converts:

```html
<table>
```

into garbage Markdown isn't very useful for research.

Represent tables explicitly:

```python
@dataclass
class Table:
    headers: list[str]
    rows: list[list[str]]
    caption: str | None
```

Then support:

```json
{
  "headers": ["Year", "Revenue"],
  "rows": [
    ["2024", "$4.2B"],
    ["2025", "$5.1B"]
  ]
}
```

And Markdown becomes just one presentation layer.

---

# 9. Add PDFs

Firecrawl explicitly supports parsing PDFs/documents. ([GitHub][1])

Your version currently treats non-HTML content as essentially:

```python
"markdown": ""
```

because of this check. 

Instead:

```text
Content-Type
     │
     ├── text/html ──────► HTML pipeline
     │
     ├── application/pdf ─► PDF pipeline
     │
     ├── application/json ─► JSON pipeline
     │
     ├── text/plain ─────► text pipeline
     │
     └── image/* ────────► optional OCR pipeline
```

That alone makes it far more useful for your research workflow.

---

# 10. Add caching

This is another major improvement.

Use:

```text
URL + options
      │
      ▼
content hash/cache key
      │
 ┌────┴────┐
 │         │
HIT       MISS
 │         │
return    fetch
           │
           ▼
         cache
```

SQLite would actually be perfect for your project.

Something like:

```sql
CREATE TABLE pages (
    url TEXT PRIMARY KEY,
    final_url TEXT,
    fetched_at TEXT,
    status_code INTEGER,
    content_hash TEXT,
    markdown TEXT,
    html TEXT,
    metadata TEXT
);
```

Then:

```bash
minicrawl scrape URL --max-age 86400
```

Firecrawl itself now emphasizes cached scraping for latency improvements. ([GitHub][3])

---

# 11. Make crawling substantially smarter

Your BFS works, but I'd change:

```text
queue
```

into a **priority frontier**.

Instead of:

```text
A
B
C
D
E
```

you could prioritize:

```text
/docs/        priority 100
/about        priority 80
/research     priority 90
/random-ad    priority 5
```

And score discovered URLs based on:

```python
priority = (
    relevance_score
    + depth_score
    + path_score
    - junk_score
)
```

Now crawling can become:

> "Find the pages most likely to answer my question."

rather than:

> "Visit everything."

---

# 12. Add URL intelligence

Automatically reject things like:

```text
/login
/logout
/cart
/search?q=...
/wp-admin
/share
/print
?utm_source=...
```

Normalize:

```text
https://example.com/page
https://example.com/page/
https://example.com/page?utm_source=x
```

into the same canonical identity where appropriate.

Your existing `normalize()` is a start, but currently only strips fragments/trailing root slash. 

---

# 13. Add retries correctly

Instead of:

```python
except Exception:
```

do:

```python
class FetchError(Exception):
    pass

class RateLimitError(FetchError):
    pass

class TimeoutError(FetchError):
    pass

class BlockedError(FetchError):
    pass
```

Then:

```python
for attempt in range(max_retries):
    try:
        ...
    except RateLimitError:
        await asyncio.sleep(backoff(attempt))
```

with:

```text
1s
2s
4s
8s
```

and jitter.

---

# 14. Per-domain rate limiting

Your current crawler has a global `concurrency=5` and optional delay. 

I'd instead track:

```text
example.com
    max concurrent = 2
    delay = 500ms

docs.example.com
    max concurrent = 4

another.com
    max concurrent = 2
```

This is much more respectful and much harder to accidentally abuse.

---

# 15. Add observability

This one is especially relevant to your AI Orchestra/runtime work.

Every scrape should emit events:

```text
crawl.started
fetch.started
fetch.completed
fetch.failed
browser.started
browser.completed
content.extracted
document.normalized
page.cached
crawl.completed
```

For example:

```python
emit(
    "fetch.completed",
    url=url,
    status=200,
    method="http",
    duration_ms=412
)
```

Then your runtime can observe:

```text
Crawler
   │
   ├── fetch.started
   ├── fetch.completed
   ├── extraction.completed
   └── document.completed
          │
          ▼
       Reader
          │
          ▼
       Auditor
```

That fits **extremely well** with the runtime architecture you've been building.

---

# 16. Then add an extraction layer

Don't make the crawler itself an LLM.

Instead:

```text
                   WebDocument
                       │
                       ▼
                 Extraction API
                       │
              ┌────────┴────────┐
              │                 │
           Schema             Prompt
              │                 │
              ▼                 ▼
        Structured JSON    LLM extraction
```

For example:

```json
{
  "url": "...",
  "schema": {
    "company": "string",
    "founders": ["string"],
    "founded": "integer"
  }
}
```

The crawler's job is:

> **Get trustworthy evidence.**

The extractor's job is:

> **Interpret evidence.**

That separation is exactly what you want if you're eventually using this for auditing.

---

# 17. Add search — but don't fake it

Firecrawl's current system also has Search, which is a major capability beyond your current implementation. ([GitHub][1])

I'd make:

```text
search/
    engine.py
    providers/
        brave.py
        bing.py
        google.py
        searxng.py
```

with:

```python
class SearchProvider(Protocol):

    async def search(
        self,
        query: str,
        limit: int
    ) -> list[SearchResult]:
        ...
```

Then your crawler can do:

```text
Search
  ↓
URLs
  ↓
Scraper
  ↓
Evidence
```

instead of pretending that crawling is search.

---

# 18. The killer feature for YOUR project: evidence mode

This is the part I'd make the centerpiece.

Add:

```bash
minicrawl research "Does X actually support Y?"
```

Instead of simply returning pages:

```json
{
  "claim": "X supports Y",
  "evidence": [
    {
      "text": "...",
      "url": "...",
      "selector": "...",
      "retrieved_at": "...",
      "confidence": 0.93
    }
  ]
}
```

And critically:

**don't let the LLM invent the citation.**

The extraction pipeline produces evidence references.

Your Auditor then reasons over them.

---

# 19. Your architecture becomes

I'd actually split your current single `minicrawl.py` into:

```text
minicrawl/
│
├── __init__.py
│
├── models.py
│
├── config.py
│
├── client.py
│
├── fetch/
│   ├── http.py
│   ├── browser.py
│   └── strategy.py
│
├── parse/
│   ├── html.py
│   ├── markdown.py
│   ├── pdf.py
│   ├── tables.py
│   └── metadata.py
│
├── crawl/
│   ├── frontier.py
│   ├── crawler.py
│   ├── robots.py
│   └── sitemap.py
│
├── cache/
│   └── sqlite.py
│
├── extraction/
│   ├── schema.py
│   └── extractor.py
│
├── search/
│   ├── engine.py
│   └── providers/
│
├── evidence/
│   ├── provenance.py
│   └── citations.py
│
├── runtime/
│   └── events.py
│
├── api.py
└── cli.py
```

**This is what I'd build rather than trying to turn your 416-line file into a 2,000-line monster.**

---

## The resulting capability matrix

| Capability              | Current `minicrawl` |                Upgraded version |
| ----------------------- | ------------------: | ------------------------------: |
| Static HTML             |                   ✅ |                               ✅ |
| Markdown                |                   ✅ |                               ✅ |
| Main-content extraction |               Basic |                    **Advanced** |
| Metadata                |                   ✅ |                               ✅ |
| Links                   |                   ✅ |                               ✅ |
| Sitemap                 |                   ✅ |                               ✅ |
| BFS crawl               |                   ✅ |              **Priority crawl** |
| Robots                  |                   ✅ |                      **Better** |
| Async                   |                   ✅ |                    **Advanced** |
| JS websites             |                   ❌ |                  **Playwright** |
| Browser interaction     |                   ❌ |                         **Yes** |
| Screenshots             |                   ❌ |                         **Yes** |
| PDFs                    |                   ❌ |                         **Yes** |
| Tables                  |               Basic |                  **Structured** |
| Caching                 |                   ❌ |                      **SQLite** |
| Retry system            |               Basic | **Typed + exponential backoff** |
| Rate limiting           |               Basic |                  **Per-domain** |
| Structured extraction   |                   ❌ |                         **Yes** |
| Search                  |                   ❌ |        **Provider abstraction** |
| Provenance              |                   ❌ |                 **First-class** |
| Evidence                |                   ❌ |                 **First-class** |
| Runtime events          |                   ❌ |                         **Yes** |
| Agent integration       |                   ❌ |                      **Native** |
| Self-hosted             |                   ✅ |                               ✅ |
| API                     |                   ✅ |                 **Much richer** |

### And there's an important distinction

I wouldn't claim that this is *literally* better than Firecrawl today.

Firecrawl has an enormous production codebase and currently supports things like search, extraction, browser interaction, document parsing, batching, caching and an agent layer. ([GitHub][1])

But **your goal shouldn't be "clone Firecrawl."**

Your goal should be:

> **Build a self-hosted web evidence engine optimized for trustworthy AI research and auditing.**

That's a much more interesting project.

And it fits your existing AI Orchestra unusually well:

```text
                    Web
                     │
                     ▼
              ┌─────────────┐
              │  MiniCrawl  │
              └──────┬──────┘
                     │
              WebDocument
                     │
                     ▼
                The_Reader
                     │
                Claims/Facts
                     │
                     ▼
                 Auditor
                     │
                     ▼
              FactHistory/SQLite
                     │
                     ▼
                Orchestrator
```

**That's where I'd take it.** Your existing 416-line implementation is a good prototype; I would not throw it away. I'd promote its current `scrape`, `crawl`, and `map` functions into the first implementations of those modules and build the stronger layers around them. 

[1]: https://github.com/firecrawl?utm_source=chatgpt.com "Firecrawl · GitHub"
[2]: https://github.com/firecrawl/firecrawl-docs/blob/main/dashboard.mdx?utm_source=chatgpt.com "firecrawl-docs/dashboard.mdx at main · firecrawl/firecrawl-docs · GitHub"
[3]: https://github.com/firecrawl/firecrawl-docs/blob/main/features/fast-scraping.mdx?utm_source=chatgpt.com "firecrawl-docs/features/fast-scraping.mdx at main · firecrawl/firecrawl-docs · GitHub"
