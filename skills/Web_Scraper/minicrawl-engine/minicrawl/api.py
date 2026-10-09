# NOTE: no `from __future__ import annotations` here: FastAPI needs real annotation objects.
import asyncio
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .client import MiniCrawl
from .config import CrawlOptions, EngineConfig, ScrapeOptions
from .errors import MiniCrawlError
from .models import CrawlResult


class ScrapeReq(BaseModel):
    url: str
    render: str = "auto"
    onlyMainContent: bool = True
    includeTags: Optional[List[str]] = None
    excludeTags: Optional[List[str]] = None
    includeHtml: bool = False
    screenshot: bool = False
    waitFor: Optional[str] = None
    actions: Optional[List[dict]] = None
    maxAge: Optional[float] = None


class CrawlReq(BaseModel):
    url: str
    limit: int = 10
    maxDepth: int = 2
    includePaths: List[str] = []
    excludePaths: List[str] = []
    allowSubdomains: bool = False
    ignoreRobotsTxt: bool = False
    useSitemap: bool = False
    keywords: List[str] = []
    render: str = "auto"
    maxAge: Optional[float] = None


class MapReq(BaseModel):
    url: str
    search: Optional[str] = None
    limit: int = 5000


class SearchReq(BaseModel):
    query: str
    limit: int = 5


class ResearchReq(BaseModel):
    question: str
    urls: Optional[List[str]] = None
    searchLimit: int = 5
    topK: int = 8


def create_app(engine: Optional[MiniCrawl] = None) -> FastAPI:
    state = {"mc": engine}

    @asynccontextmanager
    async def lifespan(_):
        yield
        if state["mc"]:
            await state["mc"].aclose()

    app = FastAPI(title="minicrawl", version="0.2.0", lifespan=lifespan)
    jobs = {}

    def mc() -> MiniCrawl:
        if state["mc"] is None:
            import os
            state["mc"] = MiniCrawl(EngineConfig(cache_path=os.getenv("MINICRAWL_CACHE")))
        return state["mc"]

    def sopts(r) -> ScrapeOptions:
        return ScrapeOptions(render=r.render, only_main_content=getattr(r, "onlyMainContent", True),
                             include_tags=getattr(r, "includeTags", None), exclude_tags=getattr(r, "excludeTags", None),
                             include_html=getattr(r, "includeHtml", False), screenshot=getattr(r, "screenshot", False),
                             wait_for=getattr(r, "waitFor", None), actions=getattr(r, "actions", None),
                             max_age=r.maxAge)

    @app.post("/v1/scrape")
    async def scrape(req: ScrapeReq):
        try:
            doc = await mc().scrape(req.url, sopts(req))
        except MiniCrawlError as e:
            raise HTTPException(502, {"error": type(e).__name__, "message": str(e), "retryable": e.retryable})
        return {"success": True, "data": doc.to_dict()}

    @app.post("/v1/crawl")
    async def crawl(req: CrawlReq):
        jid, res = str(uuid.uuid4()), CrawlResult()
        jobs[jid] = res
        o = CrawlOptions(limit=req.limit, max_depth=req.maxDepth, include_paths=req.includePaths,
                         exclude_paths=req.excludePaths, allow_subdomains=req.allowSubdomains,
                         respect_robots=not req.ignoreRobotsTxt, use_sitemap=req.useSitemap, keywords=req.keywords,
                         scrape=ScrapeOptions(render=req.render, max_age=req.maxAge))
        asyncio.create_task(mc().crawl(req.url, o, res))
        return {"success": True, "id": jid, "url": f"/v1/crawl/{jid}"}

    @app.get("/v1/crawl/{jid}")
    async def crawl_status(jid: str):
        if jid not in jobs:
            raise HTTPException(404, "job not found")
        return {"success": True, **jobs[jid].to_dict()}

    @app.post("/v1/map")
    async def map_(req: MapReq):
        return {"success": True, "links": await mc().map(req.url, req.search, req.limit)}

    @app.post("/v1/search")
    async def search(req: SearchReq):
        try:
            return {"success": True, "data": [asdict(r) for r in await mc().search(req.query, req.limit)]}
        except MiniCrawlError as e:
            raise HTTPException(503, {"error": type(e).__name__, "message": str(e)})

    @app.post("/v1/research")
    async def research(req: ResearchReq):
        try:
            rep = await mc().research(req.question, req.urls, req.searchLimit, req.topK)
        except MiniCrawlError as e:
            raise HTTPException(503, {"error": type(e).__name__, "message": str(e)})
        return {"success": True, "data": asdict(rep)}

    @app.get("/v1/events")
    async def events(since: float = 0.0):
        return {"events": [e for e in mc().bus.history if e["ts"] > since]}

    return app
