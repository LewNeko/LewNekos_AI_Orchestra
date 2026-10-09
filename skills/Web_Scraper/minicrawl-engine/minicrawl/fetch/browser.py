"""Playwright-backed fetching: JS rendering, interaction, screenshots. Loaded lazily."""
from __future__ import annotations

import asyncio
import time

from ..errors import BrowserUnavailable, FetchError, FetchTimeout
from .base import RawResponse


class BrowserFetcher:
    def __init__(self, cfg, limiter, bus):
        self.cfg, self.limiter, self.bus = cfg, limiter, bus
        self._pw = self._browser = None
        self._lock = asyncio.Lock()

    async def _ensure(self):
        async with self._lock:
            if self._browser:
                return
            try:
                from playwright.async_api import async_playwright
            except ImportError as e:
                raise BrowserUnavailable("playwright not installed: pip install playwright && playwright install chromium") from e
            try:
                self._pw = await async_playwright().start()
                self._browser = await self._pw.chromium.launch(headless=self.cfg.browser_headless)
            except Exception as e:
                if self._pw:
                    await self._pw.stop()
                    self._pw = None
                raise BrowserUnavailable(f"could not launch chromium ({e}); run: playwright install chromium") from e

    async def aclose(self):
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        self._browser = self._pw = None

    async def _run_actions(self, page, actions):
        for a in actions or []:
            t = a.get("type")
            if t == "click":
                await page.click(a["selector"])
            elif t == "fill":
                await page.fill(a["selector"], a.get("text", ""))
            elif t == "press":
                await page.keyboard.press(a["key"])
            elif t == "wait":
                await page.wait_for_timeout(int(a.get("ms", 500)))
            elif t == "wait_for":
                await page.wait_for_selector(a["selector"])
            elif t == "scroll":
                if a.get("to") == "bottom" or "pixels" not in a:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                else:
                    await page.mouse.wheel(0, int(a["pixels"]))
                await page.wait_for_timeout(int(a.get("ms", 300)))
            else:
                raise FetchError(f"unknown browser action: {t}", page.url)

    async def fetch(self, url: str, opts) -> RawResponse:
        await self._ensure()
        timeout_ms = int((opts.timeout or self.cfg.timeout) * 1000)
        self.bus.emit("browser.started", url=url)
        async with self.limiter.slot(url):
            ctx = await self._browser.new_context(user_agent=self.cfg.user_agent)
            try:
                page = await ctx.new_page()
                t0 = time.monotonic()
                try:
                    resp = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                    try:
                        await page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 8000))
                    except Exception:
                        pass  # chatty pages never go idle; use what we have
                    if opts.wait_for:
                        await page.wait_for_selector(opts.wait_for, timeout=timeout_ms)
                    await self._run_actions(page, opts.actions)
                    html = await page.content()
                    shot = await page.screenshot(full_page=True) if opts.screenshot else None
                except Exception as e:
                    if "Timeout" in type(e).__name__:
                        raise FetchTimeout(f"browser timeout: {e}", url) from e
                    raise
                ms = int((time.monotonic() - t0) * 1000)
                self.bus.emit("browser.completed", url=url, duration_ms=ms)
                return RawResponse(url=url, final_url=page.url, status=resp.status if resp else 200,
                                   content_type="text/html; charset=utf-8", body=html.encode("utf-8"),
                                   method="browser", encoding="utf-8", duration_ms=ms, screenshot=shot)
            finally:
                await ctx.close()
