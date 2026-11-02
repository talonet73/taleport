"""Week overview, Keyword trends and 'Ask'."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, ValidationError

from taleport.api.context import AppContext
from taleport.ask.plan import PRESETS
from taleport.ask.scope import Filters, Period
from taleport.core.errors import AppError

router = APIRouter()


def _ctx(request: Request) -> AppContext:
    return request.app.state.ctx


@router.get("/week")
def week(request: Request) -> dict[str, Any]:
    return _ctx(request).insights.week()


@router.get("/trends")
def trends(
    request: Request,
    period: str = "last_7_days",
    start: date | None = None,
    end: date | None = None,
    topics: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    try:
        topic_ids = [int(t) for t in topics.split(",") if t.strip()] if topics else None
        scope_period = Period(preset=period, start=start, end=end)  # type: ignore[arg-type]
        filters = Filters(topics=topic_ids or None, languages=[language] if language else None)  # type: ignore[list-item]
    except (ValueError, ValidationError) as exc:
        raise AppError("validation", fields=["period"]) from exc
    return _ctx(request).insights.trends(scope_period, filters)


@router.get("/ask/presets")
def ask_presets() -> list[str]:
    return list(PRESETS)


@router.post("/ask/preset/{preset_id}")
def ask_preset(request: Request, preset_id: str) -> dict[str, Any]:
    return _ctx(request).insights.run_preset(preset_id)


class AskBody(BaseModel):
    question: str = Field(max_length=1000)
    mode: str | None = None


class AskParse(BaseModel):
    question: str = Field("", max_length=1000)
    text: str = Field(max_length=50_000)


@router.post("/ask")
def ask(request: Request, body: AskBody) -> dict[str, Any]:
    return _ctx(request).insights.ask(body.question, body.mode)


@router.post("/ask/parse")
def ask_parse(request: Request, body: AskParse) -> dict[str, Any]:
    return _ctx(request).insights.parse_ask(body.question, body.text)
