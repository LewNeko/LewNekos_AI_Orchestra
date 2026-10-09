from __future__ import annotations

import math
import re
from collections import Counter

from .provenance import evidence_from_block

STOP = set("a an the of to in on for and or is are was were be been being by with as at from that this it its "
           "do does did how what why when who which can could should would will not no yes about into than then".split())


def tokens(s: str) -> list:
    return [t for t in re.findall(r"[a-z0-9]+", s.lower()) if t not in STOP and len(t) > 1]


def rank_blocks(query: str, docs, top_k: int = 8) -> list:
    """BM25 over every content block across the given documents. Returns Evidence with provenance."""
    q = tokens(query)
    items = [(d, b) for d in docs for b in d.blocks]
    if not q or not items:
        return []
    toks = [tokens(b.text + " " + " ".join(b.heading_path)) for _, b in items]
    N = len(items)
    avg = sum(map(len, toks)) / N or 1
    df = Counter(t for ts in toks for t in set(ts))
    k1, b_ = 1.5, 0.75
    scored = []
    for (d, b), ts in zip(items, toks):
        tf = Counter(ts)
        s = 0.0
        for t in set(q):
            if t in tf:
                idf = math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b_ + b_ * len(ts) / avg))
        if s > 0:
            scored.append((s, d, b))
    scored.sort(key=lambda x: -x[0])
    top = scored[:top_k]
    if not top:
        return []
    mx = top[0][0]
    out = []
    for i, (s, d, b) in enumerate(top, 1):
        ev = evidence_from_block(d, b, relevance=round(s / mx, 3))
        ev.id = f"e{i}"
        out.append(ev)
    return out
