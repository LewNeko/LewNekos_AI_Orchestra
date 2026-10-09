"""Cheap path first; escalate to a browser only when the HTTP result is an empty shell or a bot-wall."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..errors import BlockedError, BrowserUnavailable
from .base import RawResponse

SHELL_MARKERS = re.compile(r'id\s*=\s*["\']?(root|app|__next|__nuxt)["\']?[\s>]|ng-app|data-reactroot|webpack|<noscript', re.I)
BLOCK_PHRASES = ("just a moment", "checking your browser", "verify you are human", "captcha",
                 "access denied", "attention required", "enable javascript and cookies")


def visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "template", "svg"]):
        t.decompose()
    return " ".join(soup.get_text(" ").split())


def looks_like_js_shell(html: str) -> bool:
    text = visible_text(html)
    low = text.lower()
    if len(text) >= 300:
        return False
    return ("enable javascript" in low or "requires javascript" in low
            or bool(SHELL_MARKERS.search(html)) or len(text) < 40 and html.lower().count("<script") >= 2)


def looks_like_blocked(html: str) -> bool:
    text = visible_text(html).lower()
    return len(text) < 1200 and any(p in text for p in BLOCK_PHRASES)


def is_html(raw: RawResponse) -> bool:
    return "html" in raw.content_type.lower()


class Fetcher:
    def __init__(self, http, browser, bus):
        self.http, self.browser, self.bus = http, browser, bus

    async def fetch(self, url: str, opts) -> RawResponse:
        needs_browser = opts.render == "always" or opts.actions or opts.screenshot or opts.wait_for
        if needs_browser:
            if opts.render == "never":
                raise ValueError("browser features requested but render='never'")
            return await self.browser.fetch(url, opts)
        if opts.render == "never":
            return await self.http.fetch(url, opts.timeout)

        # auto
        try:
            raw = await self.http.fetch(url, opts.timeout)
        except BlockedError as e:
            return await self._escalate(url, opts, "blocked", None, e)
        if is_html(raw):
            html = raw.text
            if looks_like_blocked(html):
                return await self._escalate(url, opts, "bot_wall", raw)
            if looks_like_js_shell(html):
                return await self._escalate(url, opts, "js_shell", raw)
        return raw

    async def _escalate(self, url, opts, reason, raw, err=None) -> RawResponse:
        self.bus.emit("fetch.escalated", url=url, reason=reason)
        try:
            return await self.browser.fetch(url, opts)
        except BrowserUnavailable as e:
            self.bus.emit("fetch.escalation_failed", url=url, reason=reason, error=str(e))
            if raw is not None:   # degrade gracefully: return the shell, flagged
                raw.warnings.append(f"{reason}_detected_browser_unavailable")
                return raw
            raise err or e
