"""Today overview, theme detail and manual re-analysis."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from taleport.api.context import AppContext

router = APIRouter()


def _ctx(request: Request) -> AppContext:
    return request.app.state.ctx


@router.get("/today")
def today(request: Request) -> dict[str, Any]:
    return _ctx(request).analysis.today_overview()


@router.get("/themes/{theme_id}")
def theme_detail(request: Request, theme_id: int) -> dict[str, Any]:
    return _ctx(request).analysis.theme_detail(theme_id)


@router.post("/analysis/run", status_code=204)
def run_analysis(request: Request) -> None:
    """Recompute today's statistics for every active topic (e.g. after editing keywords)."""
    ctx = _ctx(request)
    for topic in ctx.topics.active():
        ctx.analysis.analyze(topic.id)
    ctx.bus.publish("analysis.finished", {})
