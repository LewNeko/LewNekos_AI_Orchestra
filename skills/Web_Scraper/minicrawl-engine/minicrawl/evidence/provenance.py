"""Evidence = text + exactly where it came from. Built from parsed blocks, never from an LLM."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Evidence:
    text: str
    source_url: str
    selector: str | None
    page_title: str | None
    retrieved_at: str
    position: int
    content_hash: str
    heading_path: list = field(default_factory=list)
    relevance: float | None = None      # lexical relevance 0..1. NOT a truth probability.
    id: str = ""


def evidence_from_block(doc, block, relevance=None) -> Evidence:
    return Evidence(text=block.text, source_url=doc.final_url, selector=block.selector, page_title=doc.title,
                    retrieved_at=doc.fetched_at, position=block.position, content_hash=doc.content_hash,
                    heading_path=list(block.heading_path), relevance=relevance)


def _norm(s: str) -> str:
    return " ".join(s.split())


def verify(ev: Evidence, docs) -> bool:
    """True only if this exact text exists in the matching document at the recorded position.
    Use before trusting any citation, whoever produced it."""
    for d in docs:
        if d.final_url == ev.source_url and d.content_hash == ev.content_hash:
            return any(b.position == ev.position and _norm(b.text) == _norm(ev.text) for b in d.blocks)
    return False
