import asyncio

import pytest

from minicrawl import CrawlOptions, EngineConfig, MiniCrawl, ScrapeOptions, verify
from minicrawl.errors import BlockedError, BrowserUnavailable, HTTPStatusError
from minicrawl.fetch.base import RawResponse
from minicrawl.crawl.urls import canonicalize, is_junk
from minicrawl.extraction.extractor import extract
from minicrawl.models import WebDocument

FAST = dict(per_domain_delay=0.0, per_domain_concurrency=4, backoff_base=0.01)


def run(coro):
    return asyncio.run(coro)


def engine(**kw):
    return MiniCrawl(EngineConfig(**{**FAST, **kw}), **{k: kw.pop(k) for k in ("browser",) if k in kw})


class FakeBrowser:
    """Stands in for Playwright so escalation logic is testable without Chromium."""
    def __init__(self): self.calls = []
    async def fetch(self, url, opts):
        self.calls.append(url)
        html = "<html><body><main><h1>Rendered</h1><p>" + "Hydrated client side content. " * 20 + "</p></main></body></html>"
        return RawResponse(url, url, 200, "text/html", html.encode(), "browser", "utf-8")
    async def aclose(self): pass


class DeadBrowser(FakeBrowser):
    async def fetch(self, url, opts):
        raise BrowserUnavailable("no chromium")


def test_scrape_main_content_tables_provenance(server):
    async def go():
        async with MiniCrawl(EngineConfig(**FAST)) as mc:
            d = await mc.scrape(server + "/docs/guide")
            assert "Login" not in d.markdown and "junk" not in d.markdown          # boilerplate stripped
            assert d.title == "Guide" and d.fetch_method == "http"
            assert d.tables[0].headers == ["Year", "Revenue"] and d.tables[0].rows[1] == ["2025", "$5.1B"]
            assert "| 2025 | $5.1B |" in d.tables[0].to_markdown()
            h2 = next(b for b in d.blocks if b.tag == "h2")
            assert h2.selector and h2.source_url.endswith("/docs/guide")
            p = next(b for b in d.blocks if b.tag == "p")
            assert p.heading_path == ["Guide"]
            assert d.to_text() and d.to_dict()["content_hash"] == d.content_hash
            assert WebDocument.from_dict(d.to_dict()).tables[0].rows == d.tables[0].rows
    run(go())


def test_typed_errors_and_retries(server):
    async def go():
        async with MiniCrawl(EngineConfig(**FAST)) as mc:
            events = []
            mc.bus.subscribe(events.append, "fetch.retry")
            assert "Flaky" in (await mc.scrape(server + "/flaky")).title            # 503, 503, then 200
            assert len(events) == 2
            assert "RL" in (await mc.scrape(server + "/ratelimited")).title         # 429 with Retry-After
            with pytest.raises(HTTPStatusError):
                await mc.scrape(server + "/missing")
            with pytest.raises(BlockedError):
                await mc.scrape(server + "/blocked", ScrapeOptions(render="never"))
    run(go())


def test_auto_escalation_to_browser(server):
    async def go():
        fb = FakeBrowser()
        async with MiniCrawl(EngineConfig(**FAST), browser=fb) as mc:
            ev = []; mc.bus.subscribe(ev.append, "fetch.escalated")
            d = await mc.scrape(server + "/spa")
            assert d.fetch_method == "browser" and "Hydrated" in d.markdown and ev[0]["reason"] == "js_shell"
            d = await mc.scrape(server + "/docs/guide")                              # cheap path: no browser
            assert d.fetch_method == "http" and len(fb.calls) == 1
            d = await mc.scrape(server + "/blocked")                                 # 403 -> browser
            assert d.fetch_method == "browser" and len(fb.calls) == 2
    run(go())


def test_graceful_degradation_without_browser(server):
    async def go():
        async with MiniCrawl(EngineConfig(**FAST), browser=DeadBrowser()) as mc:
            d = await mc.scrape(server + "/spa")
            assert "js_shell_detected_browser_unavailable" in d.metadata["warnings"]
            with pytest.raises(BlockedError):
                await mc.scrape(server + "/blocked")                                 # nothing to fall back to
    run(go())


def test_pdf_and_json(server):
    async def go():
        async with MiniCrawl(EngineConfig(**FAST)) as mc:
            d = await mc.scrape(server + "/doc.pdf")
            assert d.metadata["kind"] == "pdf" and "Revenue grew" in d.markdown and d.blocks[0].selector == "page=1"
            j = await mc.scrape(server + "/data.json")
            assert j.metadata["kind"] == "json" and '"a": 1' in j.markdown
    run(go())


def test_cache(server, tmp_path):
    async def go():
        async with MiniCrawl(EngineConfig(cache_path=str(tmp_path / "c.db"), **FAST)) as mc:
            a = await mc.scrape(server + "/random/x", ScrapeOptions(max_age=60))
            n = len([e for e in mc.bus.history if e["event"] == "fetch.completed"])
            b = await mc.scrape(server + "/random/x", ScrapeOptions(max_age=60))
            assert b.from_cache and b.fetch_method == a.fetch_method
            assert len([e for e in mc.bus.history if e["event"] == "fetch.completed"]) == n
            assert len(mc.cache.history(server + "/random/x")) == 1
    run(go())


def test_crawl_filters_robots_priority(server):
    async def go():
        async with MiniCrawl(EngineConfig(**FAST)) as mc:
            res = await mc.crawl(server, CrawlOptions(limit=10, max_depth=2, use_sitemap=False))
            urls = {p.final_url.replace(server, "") for p in res.pages}
            assert urls == {"", "/docs/guide", "/random/x"}, urls                      # login/cart/img/private/dupe excluded
            assert res.stats.skipped_robots == 1 and res.stats.skipped_filter >= 3
            assert res.status == "completed" and not res.errors

            # limit=2 with a keyword: priority frontier must pick /docs/guide over /random/x
            res = await mc.crawl(server, CrawlOptions(limit=2, keywords=["docs"]))
            assert [p.depth for p in res.pages] == [0, 1] and res.pages[1].final_url.endswith("/docs/guide")
    run(go())


def test_map_and_events(server):
    async def go():
        async with MiniCrawl(EngineConfig(**FAST)) as mc:
            links = await mc.map(server)
            assert server + "/docs/guide" in links and not any("login" in l for l in links)
            await mc.scrape(server + "/random/x")
            names = [e["event"] for e in mc.bus.history]
            assert names[-3:] == ["fetch.started", "fetch.completed", "content.extracted"]
    run(go())


def test_urls():
    assert canonicalize("HTTPS://Ex.com:443/a//b/?utm_source=x&z=1&a=2#f") == "https://ex.com/a/b?a=2&z=1"
    assert is_junk("http://a.com/wp-admin/x") and is_junk("http://a.com/search?q=1") and not is_junk("http://a.com/docs")


def test_research_evidence_is_verifiable_and_llm_cannot_invent(server):
    async def go():
        async with MiniCrawl(EngineConfig(**FAST)) as mc:
            rep = await mc.research("Who founded the platform and when?", urls=[server + "/random/x", server + "/docs/guide"])
            assert rep.evidence and "Ada Chen" in rep.evidence[0].text and rep.evidence[0].relevance == 1.0
            docs = [await mc.scrape(u) for u in rep.sources]
            assert all(verify(e, docs) for e in rep.evidence)
            forged = type(rep.evidence[0])(**{**rep.evidence[0].__dict__, "text": "Founded by Bob in 1999."})
            assert not verify(forged, docs)

            async def llm(prompt):
                return "Founded in 2014 by Ada Chen [e1]. Also a made up fact [e99]."
            rep = await mc.research("Who founded it?", urls=[server + "/random/x"], llm=llm)
            assert rep.cited == ["e1"] and rep.invalid_citations == ["e99"]
    run(go())


def test_structured_extraction_with_checked_citations(server):
    async def go():
        async with MiniCrawl(EngineConfig(**FAST)) as mc:
            doc = await mc.scrape(server + "/docs/guide")
            pos = next(b.position for b in doc.blocks if "Ada Chen" in b.text)

            async def llm(prompt):
                assert "[b%d]" % pos in prompt and "[t0]" in prompt
                return ('```json\n{"data": {"founder": "Ada Chen", "founded": "2014", "revenue": [5.1]}, '
                        f'"sources": {{"founder": ["b{pos}"], "revenue": ["t0", "b999"]}}}}\n```')
            r = await extract(doc, {"founder": "string", "founded": "integer", "revenue": ["number"]}, llm)
            assert r.data["founder"] == "Ada Chen"
            assert any("founded" in p for p in r.problems)                         # "2014" is a string, not integer
            assert r.unverified_refs == ["revenue:b999"]                           # hallucinated block id caught
            assert verify(r.evidence["founder"][0], [doc])
            assert r.evidence["revenue"][0].selector.endswith("table:nth-of-type(1)")   # table citation -> table selector
    run(go())


def test_api(server):
    from fastapi.testclient import TestClient
    from minicrawl.api import create_app
    with TestClient(create_app(MiniCrawl(EngineConfig(**FAST)))) as c:
        r = c.post("/v1/scrape", json={"url": server + "/docs/guide"}).json()
        assert r["success"] and r["data"]["tables"][0]["headers"] == ["Year", "Revenue"]
        assert c.post("/v1/scrape", json={"url": server + "/missing"}).status_code == 502
        assert c.post("/v1/map", json={"url": server}).json()["links"]
        jid = c.post("/v1/crawl", json={"url": server, "limit": 3}).json()["id"]
        import time
        for _ in range(50):
            s = c.get(f"/v1/crawl/{jid}").json()
            if s["status"] != "running":
                break
            time.sleep(0.1)
        assert s["status"] == "completed" and len(s["pages"]) == 3
        assert c.get("/v1/events").json()["events"]


def test_real_browser_fetcher_degrades_when_chromium_missing(server):
    """Default BrowserFetcher (real Playwright path): if Chromium isn't installed we still return the shell, flagged."""
    async def go():
        async with MiniCrawl(EngineConfig(**FAST)) as mc:
            d = await mc.scrape(server + "/spa")
            assert d.fetch_method in ("http", "browser")
            if d.fetch_method == "http":
                assert "js_shell_detected_browser_unavailable" in d.metadata["warnings"]
    run(go())


def test_real_chromium_render_actions_screenshot(spa_server):
    async def go():
        async with MiniCrawl(EngineConfig(**FAST)) as mc:
            try:
                d = await mc.scrape(spa_server, ScrapeOptions(wait_for="main", screenshot=True,
                                                              actions=[{"type": "click", "selector": "#b"}]))
            except BrowserUnavailable:
                pytest.skip("chromium not installed")
            assert d.fetch_method == "browser" and "Hydrated by JavaScript" in d.markdown
            assert d.screenshot_b64 and len(d.screenshot_b64) > 1000
            auto = await mc.scrape(spa_server)                      # auto-escalation on the real shell
            assert auto.fetch_method == "browser" and "Client rendered" in auto.markdown
    run(go())
