"""FastAPI-Anwendung (``uvicorn primestats.app:app``)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .accounts_api import router as accounts_router
from .api import router
from .scout_api import router as scout_router
from .config import Settings
from .ddragon import DataDragon
from .riot import MatchSource, NotFound, RiotAPIError, RiotClient
from .services import OfflineSource, PrimeStats
from .store import Store

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, *, source: MatchSource | None = None,
               store: Store | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.store = store or Store.from_url(settings.database_url)
        if settings.auto_migrate:
            from .migrate import upgrade
            upgrade(app.state.store.engine)
        src = source
        if src is None:
            if settings.demo:
                from .demo import DemoSource
                src = DemoSource()
            elif settings.api_key:
                src = RiotClient(settings.api_key, region=settings.region)
            else:
                log.warning("Kein LOL_API_KEY gesetzt – nur hochgeladene Spiele (LCU-Uploader) sind verfügbar.")
                src = OfflineSource()
        app.state.service = PrimeStats(app.state.store, src, settings.sync_match_count)
        if settings.demo and source is None:
            from .demo import import_demo_scrims, setup_demo_account
            import_demo_scrims(app.state.service, src)
            setup_demo_account(app.state.service)
        yield
        if store is None:
            app.state.store.engine.dispose()

    app = FastAPI(title="PrimeStats", version="2.0.0", lifespan=lifespan,
                  description="Statistiken für Prime-League- und Custom Games in League of Legends.")
    app.state.settings = settings
    app.state.ddragon = DataDragon(settings.cache_dir / "ddragon", fetch=settings.ddragon_fetch,
                                   language=settings.ddragon_language)
    if settings.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"],
                           allow_headers=["*"])

    @app.exception_handler(NotFound)
    async def not_found(_: Request, exc: NotFound):
        return JSONResponse({"detail": exc.message}, status_code=404)

    @app.exception_handler(RiotAPIError)
    async def riot_error(_: Request, exc: RiotAPIError):
        return JSONResponse({"detail": exc.message}, status_code=502)

    @app.get("/api/health", include_in_schema=False)
    def health():
        return {"status": "ok"}

    @app.middleware("http")
    async def csrf_guard(request: Request, call_next):
        # Cookie-authentifizierte Änderungen nur mit eigenem Header (von fremden Seiten nicht setzbar).
        # Das Uploader-Tool authentifiziert sich nicht per Cookie und ist ausgenommen.
        if (request.method not in {"GET", "HEAD", "OPTIONS"} and request.url.path.startswith("/api/")
                and not request.url.path.startswith("/api/uploader/")
                and request.headers.get("X-Requested-With") != "PrimeStats"):
            return JSONResponse({"detail": "Header X-Requested-With: PrimeStats fehlt."}, status_code=403)
        return await call_next(request)

    app.include_router(router)
    app.include_router(accounts_router)
    app.include_router(scout_router)
    if settings.frontend_dist and (settings.frontend_dist / "index.html").exists():
        _mount_frontend(app, settings.frontend_dist)
    return app


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    """Liefert das gebaute React-Frontend aus (SPA-Fallback auf index.html)."""
    assets = dist / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")
    index = dist / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)


def _default_app() -> FastAPI:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return create_app()


app = _default_app()
