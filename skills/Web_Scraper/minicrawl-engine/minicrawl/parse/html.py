from __future__ import annotations

import copy
import re
from urllib.parse import urldefrag, urljoin

from bs4 import BeautifulSoup, Comment, Tag
from markdownify import markdownify as to_md

from ..models import ContentBlock
from .tables import extract_tables

NOISE = ["script", "style", "noscript", "svg", "iframe", "template", "canvas"]
CONTROLS = ["input", "button", "select", "textarea"]
BOILER_TAGS = ["nav", "footer", "aside"]
BOILER_ROLES = {"navigation", "banner", "contentinfo", "complementary"}
BOILER_HINT = re.compile(
    r"(^|[-_ ])(nav|navbar|menu|footer|sidebar|cookie|cookies|consent|banner|advert|ads?|popup|modal|share|sharing|social|breadcrumbs?)([-_ ]|$)", re.I)
CONTENT_HINT = re.compile(r"(content|article|post|entry|main|story|text)", re.I)
BLOCK_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "pre", "blockquote", "figcaption", "dt", "dd"]
HEADING = re.compile(r"^h([1-6])$")


# ---- provenance: selectors computed against the ORIGINAL DOM, before any cleaning ----
def annotate(soup) -> dict:
    sel, stack = {}, [(soup, "")]
    while stack:
        node, path = stack.pop()
        counts: dict = {}
        for child in node.children:
            if not isinstance(child, Tag):
                continue
            counts[child.name] = counts.get(child.name, 0) + 1
            cid = child.get("id")
            if isinstance(cid, str) and re.fullmatch(r"[A-Za-z][\w-]*", cid):
                seg, p = f"{child.name}#{cid}", f"{child.name}#{cid}"
            else:
                seg = f"{child.name}:nth-of-type({counts[child.name]})"
                p = f"{path} > {seg}" if path else seg
            sel[id(child)] = p
            stack.append((child, p))
    return sel


def _sig(el) -> str:
    return " ".join([*(el.get("class") or []), el.get("id") or ""])


def extract_metadata(soup, final_url: str, status: int) -> dict:
    def meta(*names):
        for n in names:
            tag = soup.find("meta", attrs={"name": n}) or soup.find("meta", attrs={"property": n})
            if tag and tag.get("content"):
                return tag["content"].strip()
        return None

    title = soup.title.get_text(strip=True) if soup.title else None
    title = title or meta("og:title")
    if not title:
        h1 = soup.find("h1")
        title = h1.get_text(" ", strip=True) if h1 else None
    canon = soup.find("link", rel="canonical")
    html_tag = soup.find("html")
    return {"title": title, "description": meta("description", "og:description"),
            "language": html_tag.get("lang") if html_tag else None, "ogImage": meta("og:image"),
            "keywords": meta("keywords"), "canonical": canon.get("href") if canon else None,
            "sourceURL": final_url, "statusCode": status}


def extract_links(soup, base: str) -> list:
    seen, out = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#", "data:")):
            continue
        full = urldefrag(urljoin(base, href))[0]
        if full.startswith(("http://", "https://")) and full not in seen:
            seen.add(full)
            out.append(full)
    return out


def _clean(soup, exclude_tags):
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for t in soup.find_all(NOISE + CONTROLS):
        t.decompose()
    for sel in exclude_tags or []:
        for t in soup.select(sel):
            t.decompose()


def _strip_boilerplate(root):
    for t in root.find_all(BOILER_TAGS):
        t.decompose()
    for t in root.find_all("header"):
        if t.attrs is not None and not t.find_parent(["article", "main"]):
            t.decompose()
    for t in root.find_all(True):
        if t.attrs is None:
            continue
        sig = _sig(t)
        if (sig and BOILER_HINT.search(sig)) or t.get("role") in BOILER_ROLES:
            t.decompose()


def _score(el) -> float:
    text = el.get_text(" ", strip=True)
    n = len(text)
    if n < 80:
        return 0.0
    link_len = sum(len(a.get_text(" ", strip=True)) for a in el.find_all("a"))
    density = link_len / n
    paras = len(el.find_all("p"))
    heads = len(el.find_all(HEADING))
    base = n * (1 - density) ** 2 + 30 * paras + 15 * heads
    mult = {"main": 1.3, "article": 1.25, "body": 0.6}.get(el.name, 1.0)
    if el.get("role") == "main":
        mult = 1.3
    if CONTENT_HINT.search(_sig(el)):
        mult *= 1.15
    return base * mult


def pick_root(body):
    cands = [body, *body.find_all(["main", "article"])]
    for el in body.find_all(["div", "section"]):
        if CONTENT_HINT.search(_sig(el)) or el.get("role") == "main" or len(el.find_all("p")) >= 3:
            cands.append(el)
    seen, best, best_score = set(), body, -1.0
    for el in cands:
        if id(el) in seen:
            continue
        seen.add(id(el))
        s = _score(el)
        if s > best_score:
            best, best_score = el, s
    return best


def _absolutize(root, base):
    for a in root.find_all("a", href=True):
        a["href"] = urljoin(base, a["href"])
    for img in root.find_all("img"):
        src = img.get("src") or img.get("data-src")
        if src:
            img["src"] = urljoin(base, src)


def _blocks(root, sel_map, url) -> list:
    blocks, path, pos = [], [], 0
    for el in root.find_all(BLOCK_TAGS):
        if el.find_parent("table"):
            continue
        if el.name == "blockquote" and el.find("p"):
            continue
        sel = sel_map.get(id(el))          # before any copy, so provenance points at the real DOM node
        if el.name == "li":
            if el.find("p"):
                continue
            if el.find(["ul", "ol"]):
                el = copy.copy(el)
                for sub in el.find_all(["ul", "ol"]):
                    sub.decompose()
        text = el.get_text("\n" if el.name == "pre" else " ", strip=True)
        text = text if el.name == "pre" else " ".join(text.split())
        if not text:
            continue
        m = HEADING.match(el.name)
        if m:
            lvl = int(m.group(1))
            path = [(l, t) for l, t in path if l < lvl] + [(lvl, text)]
        blocks.append(ContentBlock(text=text, tag=el.name, selector=sel, source_url=url,
                                   position=pos, heading_path=[t for _, t in path]))
        pos += 1
    return blocks


def parse_html(html: str, final_url: str, status: int, only_main: bool = True, include_tags=None,
               exclude_tags=None, include_html: bool = False) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    base_tag = soup.find("base", href=True)
    base = urljoin(final_url, base_tag["href"]) if base_tag else final_url
    sel_map = annotate(soup)
    meta = extract_metadata(soup, final_url, status)
    links = extract_links(soup, base)

    _clean(soup, exclude_tags)
    body = soup.body or soup
    if include_tags:
        wrapper = BeautifulSoup("<div></div>", "html.parser").div
        for sel in include_tags:
            for t in body.select(sel):
                wrapper.append(t.extract())
        root = wrapper
    elif only_main:
        _strip_boilerplate(body)
        root = pick_root(body)
        if len(root.get_text(strip=True)) < 50:        # over-eager stripping: retry unfiltered
            return parse_html(html, final_url, status, False, None, exclude_tags, include_html)
    else:
        root = body

    _absolutize(root, base)
    md = to_md(str(root), heading_style="ATX", bullets="-", strip=["span"])
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    images, seen = [], set()
    for img in root.find_all("img", src=True):
        if not img["src"].startswith("data:") and img["src"] not in seen:
            seen.add(img["src"])
            images.append(img["src"])
    return {"title": meta["title"], "description": meta["description"], "language": meta["language"],
            "markdown": md, "html": str(root) if include_html else None, "links": links, "images": images,
            "blocks": _blocks(root, sel_map, final_url), "tables": extract_tables(root, sel_map),
            "metadata": meta}
