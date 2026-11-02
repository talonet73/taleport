"""FastAPI application factory.

Security model: the server binds to 127.0.0.1 only; every /api request must carry the
per-launch session token (header `X-TALeport-Token`, or `?t=` for the SSE stream, which
EventSource cannot send headers on); requests whose Host is not a loopback name are
rejected to block DNS-rebinding attacks from web pages.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response

from taleport.api import (
    ai_routes,
    analysis_routes,
    generator_routes,
    insights_routes,
    routes,
    scan_routes,
    sse,
    topics_routes,
)
from taleport.api.context import AppContext
from taleport.core.errors import AppError
from taleport.core.paths import frontend_dist

log = logging.getLogger(__name__)

TOKEN_HEADER = "X-TALeport-Token"
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "[::1]"}


def _host_name(host_header: str) -> str:
    if host_header.startswith("["):
        return host_header.split("]")[0] + "]"
    return host_header.rsplit(":", 1)[0]


def create_app(ctx: AppContext, static_dir: Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        ctx.bus.bind_loop(asyncio.get_running_loop())
        yield

    app = FastAPI(
        title="TALeport", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan
    )
    app.state.ctx = ctx

    @app.middleware("http")
    async def guard(request: Request, call_next):  # type: ignore[no-untyped-def]
        if _host_name(request.headers.get("host", "")) not in _LOOPBACK_HOSTS:
            return JSONResponse(AppError("forbidden", 403).to_payload(), status_code=403)
        if request.url.path.startswith("/api/"):
            supplied = request.headers.get(TOKEN_HEADER) or request.query_params.get("t") or ""
            if not secrets.compare_digest(supplied, ctx.token):
                return JSONResponse(AppError("unauthorized", 401).to_payload(), status_code=401)
        return await call_next(request)

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(exc.to_payload(), status_code=exc.status)

    @app.exception_handler(Exception)
    async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
        log.exception("Unhandled error", exc_info=exc)
        return JSONResponse(AppError("internal", 500).to_payload(), status_code=500)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = sorted({str(err["loc"][-1]) for err in exc.errors() if err.get("loc")})
        return JSONResponse(AppError("validation", fields=fields).to_payload(), status_code=400)

    app.include_router(routes.router, prefix="/api")
    app.include_router(topics_routes.router, prefix="/api")
    app.include_router(scan_routes.router, prefix="/api")
    app.include_router(analysis_routes.router, prefix="/api")
    app.include_router(ai_routes.router, prefix="/api")
    app.include_router(generator_routes.router, prefix="/api")
    app.include_router(insights_routes.router, prefix="/api")
    app.include_router(sse.router, prefix="/api")

    _mount_frontend(app, static_dir or frontend_dist())
    return app


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    """Serve the built UI with single-page-app fallback to index.html."""
    index = dist / "index.html"
    root = dist.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend(path: str) -> Response:
        if path.startswith("api/"):
            raise AppError("not_found", 404)
        if not index.is_file():
            return JSONResponse(AppError("frontend_missing", 503).to_payload(), status_code=503)
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-store"})
