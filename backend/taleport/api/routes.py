"""Core API routes: settings, secrets, app status."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from taleport.api.context import AppContext
from taleport.core.errors import AppError
from taleport.core.settings import AppSettings

router = APIRouter()


def _ctx(request: Request) -> AppContext:
    return request.app.state.ctx


@router.get("/health")
def health(request: Request) -> dict[str, Any]:
    ctx = _ctx(request)
    return {"ok": True, "version": ctx.version, "schema_version": ctx.db.schema_version()}


@router.get("/status")
def status(request: Request) -> dict[str, Any]:
    """Data for the sidebar status box."""
    ctx = _ctx(request)
    next_run = ctx.next_scan_at()
    return {
        "version": ctx.version,
        "scan_running": ctx.scans.is_running(),
        "last_scan_at": ctx.scans.last_finished_at(),
        "next_scan_at": next_run.isoformat() if next_run else None,
        "api_spend_month": round(ctx.usage.month_total(), 4),
        "api_spend_currency": "USD",
    }


@router.get("/settings")
def get_settings(request: Request) -> AppSettings:
    return _ctx(request).settings.get()


@router.patch("/settings")
def update_settings(request: Request, changes: dict[str, Any]) -> AppSettings:
    ctx = _ctx(request)
    updated = ctx.settings.update(changes)
    ctx.bus.publish("settings.changed", updated.model_dump())
    return updated


@router.get("/secrets")
def secrets_status(request: Request) -> dict[str, bool]:
    return _ctx(request).secrets.status()


class SecretValue(BaseModel):
    value: str


@router.put("/secrets/{name}", status_code=204)
def set_secret(request: Request, name: str, body: SecretValue) -> None:
    _ctx(request).secrets.set(name, body.value)


@router.delete("/secrets/{name}", status_code=204)
def delete_secret(request: Request, name: str) -> None:
    _ctx(request).secrets.delete(name)


class OpenUrl(BaseModel):
    url: str


@router.post("/app/open-url", status_code=204)
def open_url(request: Request, body: OpenUrl) -> None:
    """Open a link in the user's default browser (only http/https)."""
    if not body.url.startswith(("https://", "http://")):
        raise AppError("invalid_url")
    _ctx(request).open_url(body.url)


@router.post("/app/focus", status_code=204)
def focus_window(request: Request) -> None:
    """Called by a second launch of the app to bring the existing window forward."""
    on_focus = _ctx(request).on_focus
    if on_focus:
        on_focus()
