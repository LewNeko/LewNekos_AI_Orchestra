from __future__ import annotations

from dataclasses import dataclass, field, asdict
import hashlib
import json


@dataclass
class EngineConfig:
    user_agent: str = "minicrawl/0.2 (+self-hosted evidence engine)"
    timeout: float = 25.0
    max_retries: int = 3
    backoff_base: float = 1.0           # 1s, 2s, 4s, 8s ... plus jitter
    backoff_max: float = 30.0
    max_bytes: int = 15_000_000
    per_domain_concurrency: int = 2
    per_domain_delay: float = 0.5       # min seconds between request starts per host
    domain_overrides: dict = field(default_factory=dict)  # {"docs.x.com": {"concurrency": 4, "delay": 0.1}}
    cache_path: str | None = None       # e.g. "minicrawl_cache.sqlite"
    browser_headless: bool = True


@dataclass
class ScrapeOptions:
    render: str = "auto"                # "auto" | "always" | "never"
    only_main_content: bool = True
    include_tags: list | None = None    # CSS selectors to keep exclusively
    exclude_tags: list | None = None    # CSS selectors to drop
    include_html: bool = False
    screenshot: bool = False
    wait_for: str | None = None         # CSS selector to wait for (browser)
    actions: list | None = None         # [{"type":"click","selector":"..."}, ...]
    max_age: float | None = None        # seconds; serve from cache if younger. None = never read cache
    timeout: float | None = None

    def fingerprint(self) -> str:
        d = asdict(self)
        d.pop("max_age")
        return json.dumps(d, sort_keys=True)


@dataclass
class CrawlOptions:
    limit: int = 10
    max_depth: int = 2
    include_paths: list = field(default_factory=list)   # regexes on URL path
    exclude_paths: list = field(default_factory=list)
    allow_subdomains: bool = False
    respect_robots: bool = True
    concurrency: int = 5
    use_sitemap: bool = False
    keywords: list = field(default_factory=list)         # boosts matching URLs in the frontier
    scrape: ScrapeOptions = field(default_factory=ScrapeOptions)


def cache_key(url: str, opts: ScrapeOptions) -> str:
    return hashlib.sha256((url + "\n" + opts.fingerprint()).encode()).hexdigest()
