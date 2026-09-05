"""FastAPI application entrypoint.

Run with: python main.py (equivalent to `uvicorn main:app --reload`,
just without typing the longer command every time).
"""
from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from starlette.staticfiles import StaticFiles

from app.api import auth, contracts, dashboard, deadlines, reviews, risks
from app.database.database import init_db
from app.logging_config import configure_logging
from config import get_settings

configure_logging()
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    logger.info("startup complete")
    yield
    logger.info("shutting down")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    @app.middleware("http")
    async def log_requests(request: Request, call_next) -> Response:
        started = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - started) * 1000
        logger.info(
            "%s %s -> %d (%.1fms)", request.method, request.url.path, response.status_code, duration_ms
        )
        return response

    @app.exception_handler(Exception)
    async def log_unhandled_exception(request: Request, exc: Exception) -> Response:
        logger.exception("unhandled exception on %s %s", request.method, request.url.path)
        return Response("Internal Server Error", status_code=500)

    app.include_router(auth.router)
    app.include_router(contracts.router)
    app.include_router(risks.router)
    app.include_router(deadlines.router)
    app.include_router(reviews.router)
    app.include_router(dashboard.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "app": settings.app_name}

    # Mounted last: Starlette tries routes in registration order, so the
    # API routes above always win their exact paths first, and everything
    # else (/, /style.css, /app.js) falls through to the static frontend.
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        # Without this, the reload watcher treats our own log/upload
        # writes (logs/app.log growing on every request, documents/
        # gaining a file on every upload) as source changes and restarts
        # the app — the "N changes detected" spam this excludes.
        reload_excludes=["logs/*", "documents/*"],
    )
