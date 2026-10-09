from __future__ import annotations

import hashlib
import json

from ..models import ContentBlock, WebDocument
from .html import parse_html
from .pdf import parse_pdf


def detect_kind(content_type: str, body: bytes) -> str:
    ct = content_type.lower()
    head = body[:512].lstrip().lower()
    if "pdf" in ct or body[:5] == b"%PDF-":
        return "pdf"
    if "json" in ct:
        return "json"
    if "html" in ct or head.startswith((b"<!doctype html", b"<html")) or ("xml" in ct and b"<html" in head):
        return "html"
    if ct.startswith("text/") or "xml" in ct:
        return "text"
    if not ct and head.startswith((b"{", b"[")):
        return "json"
    return "other"


def _simple(markdown: str, url: str, blocks_text: list, title=None) -> dict:
    blocks = [ContentBlock(text=t, tag="p", selector=None, source_url=url, position=i) for i, t in enumerate(blocks_text)]
    return {"title": title, "description": None, "language": None, "markdown": markdown, "html": None,
            "links": [], "images": [], "blocks": blocks, "tables": [], "metadata": {}}


def parse_response(raw, opts, depth=None) -> WebDocument:
    kind = detect_kind(raw.content_type, raw.body)
    if kind == "html":
        d = parse_html(raw.text, raw.final_url, raw.status, opts.only_main_content, opts.include_tags,
                       opts.exclude_tags, opts.include_html)
    elif kind == "pdf":
        d = parse_pdf(raw.body, raw.final_url)
    elif kind == "json":
        try:
            pretty = json.dumps(json.loads(raw.text), indent=2, ensure_ascii=False)
        except ValueError:
            pretty = raw.text
        d = _simple(f"```json\n{pretty}\n```", raw.final_url, [pretty])
    elif kind == "text":
        text = raw.text.strip()
        d = _simple(text, raw.final_url, [p.strip() for p in text.split("\n\n") if p.strip()])
    else:
        d = _simple("", raw.final_url, [])
    d["metadata"] = {**d["metadata"], "kind": kind, "contentType": raw.content_type, "statusCode": raw.status}
    if raw.warnings:
        d["metadata"]["warnings"] = list(raw.warnings)
    text = " ".join(b.text for b in d["blocks"]) or d["markdown"]
    import base64
    return WebDocument(url=raw.url, final_url=raw.final_url, status_code=raw.status,
                       content_type=raw.content_type, fetch_method=raw.method, depth=depth,
                       word_count=len(text.split()), content_hash=hashlib.sha256(d["markdown"].encode()).hexdigest(),
                       screenshot_b64=base64.b64encode(raw.screenshot).decode() if raw.screenshot else None, **d)
