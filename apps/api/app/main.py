import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.mcp_server import build_mcp_app, mcp
from app.routers import accounts, auth, media, posts, settings
from app.services.errors import DomainError
from app.worker import run_forever


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker = asyncio.create_task(run_forever()) if get_settings().embed_worker else None
    try:
        async with mcp.session_manager.run():
            yield
    finally:
        if worker is not None:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker


def _configure_logging() -> None:
    """Uvicorn only sets up its own loggers: give ours (worker, publisher) an output."""
    log = logging.getLogger("cadence")
    if log.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False


def create_app() -> FastAPI:
    s = get_settings()
    _configure_logging()
    app = FastAPI(title="Cadence API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[s.web_base_url.rstrip("/")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse({"detail": exc.message}, status_code=exc.status)

    @app.get("/api/health")
    async def health() -> dict:
        return {"ok": True}

    for module in (auth, accounts, media, posts, settings):
        app.include_router(module.router)

    if (media_dir := media.local_media_dir()) is not None:
        Path(media_dir).mkdir(parents=True, exist_ok=True)
        app.mount("/media-files", StaticFiles(directory=media_dir), name="media-files")

    app.mount("/mcp", build_mcp_app())
    return app


app = create_app()
