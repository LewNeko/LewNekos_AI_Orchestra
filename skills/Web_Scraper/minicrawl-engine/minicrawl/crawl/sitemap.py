from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from .urls import canonicalize


async def sitemap_urls(client, base: str, limit: int = 5000) -> list:
    p = urlparse(base)
    root = f"{p.scheme}://{p.netloc}"
    queue, seen, urls = [urljoin(root, "/sitemap.xml")], set(), []
    try:
        r = await client.get(urljoin(root, "/robots.txt"))
        queue += re.findall(r"(?im)^sitemap:\s*(\S+)", r.text)
    except Exception:
        pass
    while queue and len(urls) < limit:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        try:
            r = await client.get(sm)
            if r.status_code != 200:
                continue
        except Exception:
            continue
        for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", r.text, re.S):
            (queue if loc.endswith(".xml") else urls).append(loc)
    return [canonicalize(u) for u in urls[:limit]]
