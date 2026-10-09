from __future__ import annotations

from ..models import Table


def _cell(c) -> str:
    return " ".join(c.get_text(" ", strip=True).split())


def extract_tables(root, sel_map: dict) -> list:
    out = []
    for t in root.find_all("table"):
        if t.find_parent("table"):          # nested layout tables: skip
            continue
        rows = []
        for tr in t.find_all("tr"):
            if tr.find_parent("table") is not t:
                continue
            cells = tr.find_all(["th", "td"], recursive=False) or tr.find_all(["th", "td"])
            rows.append(([_cell(c) for c in cells], all(c.name == "th" for c in cells) and bool(cells)))
        if not rows:
            continue
        headers: list = []
        if t.find("thead") and rows and rows[0][1]:
            headers, rows = rows[0][0], rows[1:]
        elif rows[0][1]:
            headers, rows = rows[0][0], rows[1:]
        cap = t.find("caption")
        out.append(Table(headers=headers, rows=[r for r, _ in rows],
                         caption=_cell(cap) if cap else None, selector=sel_map.get(id(t))))
    return out
