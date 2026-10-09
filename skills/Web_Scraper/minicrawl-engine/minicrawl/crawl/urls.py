"""URL intelligence: canonical identity, junk rejection, frontier priority."""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING = re.compile(r"^(utm_.*|fbclid|gclid|msclkid|mc_cid|mc_eid|ref|ref_src|igshid|yclid|_hsenc|_hsmi)$", re.I)
JUNK_QUERY = {"replytocom", "share", "print", "action", "sessionid", "phpsessid"}
JUNK_PATH = re.compile(
    r"(^|/)(login|logout|signin|signup|sign-in|sign-up|register|cart|checkout|wp-admin|wp-login\.php|xmlrpc\.php|"
    r"share|print|feed|account|unsubscribe|search)(/|$)", re.I)
JUNK_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".css", ".js", ".zip", ".gz", ".tar", ".exe",
            ".dmg", ".mp3", ".mp4", ".avi", ".mov", ".woff", ".woff2", ".ttf", ".xml", ".rss"}
GOOD_PATH = re.compile(r"(^|/)(docs?|guide|guides|research|about|paper|papers|blog|learn|reference|api|faq)(/|$)", re.I)


def canonicalize(url: str) -> str:
    p = urlparse(url.strip())
    netloc = p.netloc.lower()
    for scheme, port in (("http", ":80"), ("https", ":443")):
        if p.scheme.lower() == scheme and netloc.endswith(port):
            netloc = netloc[: -len(port)]
    path = re.sub(r"/{2,}", "/", p.path)
    path = path.rstrip("/") if path != "/" else ""
    q = sorted((k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not TRACKING.match(k))
    return urlunparse((p.scheme.lower(), netloc, path, "", urlencode(q), ""))


def is_junk(url: str) -> str | None:
    p = urlparse(url)
    if JUNK_PATH.search(p.path):
        return "junk_path"
    if any(p.path.lower().endswith(e) for e in JUNK_EXT):
        return "junk_extension"
    if {k.lower() for k, _ in parse_qsl(p.query)} & JUNK_QUERY:
        return "junk_query"
    if len(p.query) > 200:
        return "long_query"
    return None


def url_priority(url: str, depth: int, keywords=()) -> float:
    p = urlparse(url)
    score = 50.0 - 10 * depth
    if GOOD_PATH.search(p.path):
        score += 15
    low = url.lower()
    score += 25 * sum(1 for k in keywords if k.lower() in low)
    score -= 2 * max(0, p.path.count("/") - 2)
    score -= 5 if p.query else 0
    return score


def same_site(a: str, b: str, allow_subdomains: bool = False) -> bool:
    ha, hb = urlparse(a).netloc.lower(), urlparse(b).netloc.lower()
    return ha == hb or (allow_subdomains and (ha.endswith("." + hb) or hb.endswith("." + ha)))
