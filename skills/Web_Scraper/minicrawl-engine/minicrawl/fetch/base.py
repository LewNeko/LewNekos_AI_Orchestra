from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RawResponse:
    url: str
    final_url: str
    status: int
    content_type: str
    body: bytes
    method: str                      # "http" | "browser"
    encoding: str | None = None
    duration_ms: int = 0
    screenshot: bytes | None = None
    warnings: list = field(default_factory=list)

    @property
    def text(self) -> str:
        return self.body.decode(self.encoding or "utf-8", errors="replace")
