"""Scans, quota and the user-visible log."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from taleport.api.context import AppContext

router = APIRouter()


def _ctx(request: Request) -> AppContext:
    return request.app.state.ctx


class StartScan(BaseModel):
    topic_id: int | None = None


@router.post("/scans", status_code=202)
def start_scan(request: Request, body: StartScan) -> dict[str, int]:
    return {"scan_id": _ctx(request).scans.start("manual", body.topic_id)}


@router.get("/scans/current")
def current_scan(request: Request) -> dict[str, Any] | None:
    return _ctx(request).scans.current()


@router.post("/scans/current/cancel", status_code=204)
def cancel_scan(request: Request) -> None:
    _ctx(request).scans.cancel()


@router.get("/scans")
def scan_history(request: Request, limit: int = 20) -> list[dict[str, Any]]:
    return _ctx(request).scans.history(min(max(limit, 1), 200))


@router.get("/quota/youtube")
def youtube_quota(request: Request) -> dict[str, Any]:
    return _ctx(request).quota.status()
