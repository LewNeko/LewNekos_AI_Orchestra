from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ContentBlock:
    """One addressable unit of text, with the origin needed for provenance."""
    text: str
    tag: str
    selector: str | None
    source_url: str
    position: int
    heading_path: list = field(default_factory=list)


@dataclass
class Table:
    headers: list
    rows: list
    caption: str | None = None
    selector: str | None = None

    def to_markdown(self) -> str:
        if not self.headers and not self.rows:
            return ""
        width = max([len(self.headers)] + [len(r) for r in self.rows])
        pad = lambda r: [*r, *[""] * (width - len(r))]
        esc = lambda c: str(c).replace("|", "\\|").replace("\n", " ")
        head = pad(self.headers) if self.headers else [""] * width
        lines = ["| " + " | ".join(map(esc, head)) + " |", "|" + "---|" * width]
        lines += ["| " + " | ".join(map(esc, pad(r))) + " |" for r in self.rows]
        return "\n".join(lines)


@dataclass
class WebDocument:
    url: str
    final_url: str
    status_code: int
    content_type: str
    fetch_method: str                    # "http" | "browser" | "cache"
    title: str | None = None
    description: str | None = None
    language: str | None = None
    markdown: str = ""
    html: str | None = None
    links: list = field(default_factory=list)
    images: list = field(default_factory=list)
    blocks: list = field(default_factory=list)       # list[ContentBlock]
    tables: list = field(default_factory=list)       # list[Table]
    screenshot_b64: str | None = None
    metadata: dict = field(default_factory=dict)
    fetched_at: str = field(default_factory=utcnow)
    depth: int | None = None
    word_count: int = 0
    content_hash: str = ""
    from_cache: bool = False

    # -- representations from one parse ---------------------------------
    def to_markdown(self) -> str:
        return self.markdown

    def to_text(self) -> str:
        return "\n\n".join(b.text for b in self.blocks)

    def to_html(self) -> str | None:
        return self.html

    def to_dict(self) -> dict:
        return asdict(self)

    to_json = to_dict

    @classmethod
    def from_dict(cls, d: dict) -> "WebDocument":
        d = dict(d)
        d["blocks"] = [ContentBlock(**b) for b in d.get("blocks", [])]
        d["tables"] = [Table(**t) for t in d.get("tables", [])]
        return cls(**d)


@dataclass
class CrawlError:
    url: str
    kind: str
    message: str
    retryable: bool = False
    status: int | None = None


@dataclass
class CrawlStats:
    started_at: float = 0.0
    finished_at: float = 0.0
    discovered: int = 0
    skipped_robots: int = 0
    skipped_filter: int = 0
    cache_hits: int = 0

    @property
    def duration_s(self) -> float:
        return (self.finished_at or 0) - self.started_at if self.started_at else 0.0


@dataclass
class CrawlResult:
    start_url: str = ""
    status: str = "running"             # running | completed | failed
    pages: list = field(default_factory=list)       # list[WebDocument]
    errors: list = field(default_factory=list)      # list[CrawlError]
    stats: CrawlStats = field(default_factory=CrawlStats)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["stats"]["duration_s"] = self.stats.duration_s
        return d
