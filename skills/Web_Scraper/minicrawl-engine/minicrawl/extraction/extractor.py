"""Interpretation layer. The crawler gets evidence; the extractor interprets it, with citations that
are checked against the parsed document rather than trusted."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

from ..errors import ExtractionError
from ..evidence.provenance import evidence_from_block
from .schema import validate


@dataclass
class ExtractionResult:
    data: dict | None
    evidence: dict = field(default_factory=dict)       # field -> list[Evidence] (verified)
    unverified_refs: list = field(default_factory=list)  # block ids the model cited that don't exist
    problems: list = field(default_factory=list)


def build_prompt(doc, schema, prompt, max_chars=24000) -> str:
    lines, used = [], 0
    for b in doc.blocks:
        line = f"[b{b.position}] ({' > '.join(b.heading_path)}) {b.text}"
        used += len(line)
        if used > max_chars:
            break
        lines.append(line)
    for i, t in enumerate(doc.tables):
        lines.append(f"[t{i}] TABLE {t.caption or ''}\n{t.to_markdown()}")
    task = prompt or "Extract the requested fields."
    return (f"{task}\n\nSchema (JSON): {json.dumps(schema)}\n\n"
            "Use ONLY the numbered blocks below. If a field is not stated, use null. Reply with JSON only:\n"
            '{"data": <object matching the schema>, "sources": {"<field>": ["b3", "t0"]}}\n'
            "Every non-null field MUST list the block ids that support it.\n\n"
            f"PAGE: {doc.title or doc.final_url}\n" + "\n".join(lines))


def _parse_json(text: str):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except ValueError as e:
        raise ExtractionError(f"model did not return valid JSON: {e}") from e


async def extract(doc, schema: dict, llm, prompt: str | None = None) -> ExtractionResult:
    raw = _parse_json(await llm(build_prompt(doc, schema, prompt)))
    res = ExtractionResult(data=raw.get("data"))
    res.problems = validate(res.data, schema)
    by_pos = {b.position: b for b in doc.blocks}
    for fld, refs in (raw.get("sources") or {}).items():
        for ref in refs if isinstance(refs, list) else [refs]:
            m = re.fullmatch(r"([bt])(\d+)", str(ref))
            if m and m.group(1) == "b" and int(m.group(2)) in by_pos:
                res.evidence.setdefault(fld, []).append(evidence_from_block(doc, by_pos[int(m.group(2))]))
            elif m and m.group(1) == "t" and int(m.group(2)) < len(doc.tables):
                from ..models import ContentBlock
                t = doc.tables[int(m.group(2))]
                blk = ContentBlock(t.to_markdown(), "table", t.selector, doc.final_url, int(m.group(2)))
                res.evidence.setdefault(fld, []).append(evidence_from_block(doc, blk))
            else:
                res.unverified_refs.append(f"{fld}:{ref}")
    return res


def anthropic_llm(model: str = "claude-sonnet-4-6", api_key: str | None = None, max_tokens: int = 2000):
    """Adapter: returns an async callable(prompt)->str for extract()/research()."""
    import httpx
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ExtractionError("set ANTHROPIC_API_KEY or pass api_key")

    async def call(prompt: str) -> str:
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post("https://api.anthropic.com/v1/messages",
                             headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                             json={"model": model, "max_tokens": max_tokens,
                                   "messages": [{"role": "user", "content": prompt}]})
            r.raise_for_status()
        return "".join(p.get("text", "") for p in r.json()["content"])

    return call
