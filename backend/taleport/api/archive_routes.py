"""Archive (search), post results, calendar and notifications."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from taleport.api.context import AppContext

router = APIRouter()


def _ctx(request: Request) -> AppContext:
    return request.app.state.ctx


# -- archive -------------------------------------------------------------------------


@router.get("/archive/posts")
def archive_posts(
    request: Request,
    q: str | None = None,
    status: str | None = None,
    platform: str | None = None,
    topic_id: int | None = None,
    start: date | None = None,
    end: date | None = None,
    limit: int = 30,
    offset: int = 0,
) -> dict[str, Any]:
    return _ctx(request).archive.posts(
        q, status, platform, topic_id, start, end, min(max(limit, 1), 100), max(offset, 0)
    )


@router.get("/archive/themes")
def archive_themes(
    request: Request,
    q: str | None = None,
    topic_id: int | None = None,
    start: date | None = None,
    end: date | None = None,
    limit: int = 30,
    offset: int = 0,
) -> dict[str, Any]:
    return _ctx(request).archive.themes(
        q, topic_id, start, end, min(max(limit, 1), 100), max(offset, 0)
    )


# -- results -------------------------------------------------------------------------


class Results(BaseModel):
    likes: int | None = Field(None, ge=0)
    comments: int | None = Field(None, ge=0)
    shares: int | None = Field(None, ge=0)
    views: int | None = Field(None, ge=0)


@router.put("/drafts/{draft_id}/results")
def save_results(request: Request, draft_id: int, body: Results) -> dict[str, Any]:
    ctx = _ctx(request)
    saved = ctx.results.save(draft_id, body.model_dump())
    ctx.bus.publish("drafts.changed", {"id": draft_id})
    return {"results": saved}


@router.get("/results/summary")
def results_summary(request: Request) -> dict[str, Any]:
    return _ctx(request).results.summary()


# -- calendar ------------------------------------------------------------------------


@router.get("/calendar")
def calendar(request: Request, start: date, end: date) -> dict[str, Any]:
    return _ctx(request).planner.calendar(start, end)


class Move(BaseModel):
    day: date
    time: str | None = Field(None, max_length=5)


@router.put("/calendar/{draft_id}")
def move(request: Request, draft_id: int, body: Move) -> dict[str, Any]:
    ctx = _ctx(request)
    draft = ctx.planner.move(draft_id, body.day, body.time)
    ctx.bus.publish("drafts.changed", {"id": draft_id})
    return draft


@router.get("/posting-times")
def posting_times(request: Request) -> list[dict[str, Any]]:
    return _ctx(request).planner.posting_times()


# -- notifications -------------------------------------------------------------------


@router.get("/notifications")
def notifications(request: Request, limit: int = 30) -> dict[str, Any]:
    return _ctx(request).notifications.list(min(max(limit, 1), 100))


class MarkRead(BaseModel):
    ids: list[int] | None = None  # None = all


@router.post("/notifications/read", status_code=204)
def mark_read(request: Request, body: MarkRead) -> None:
    _ctx(request).notifications.mark_read(body.ids)


@router.delete("/notifications/read", status_code=204)
def clear_read(request: Request) -> None:
    _ctx(request).notifications.clear()
