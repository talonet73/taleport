"""Topics and collected items."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from taleport.api.context import AppContext
from taleport.topics.editions import EDITIONS
from taleport.topics.models import MAX_STYLE_EXAMPLES, MAX_TOPICS, Topic

router = APIRouter()


def _ctx(request: Request) -> AppContext:
    return request.app.state.ctx


@router.get("/topics/meta")
def topics_meta() -> dict[str, Any]:
    return {
        "max_topics": MAX_TOPICS,
        "max_style_examples": MAX_STYLE_EXAMPLES,
        "editions": [
            {"code": e.code, "language": e.language, "country": e.country}
            for e in EDITIONS.values()
        ],
    }


@router.get("/topics")
def list_topics(request: Request) -> list[dict[str, Any]]:
    ctx = _ctx(request)
    # linked_at is stored in UTC: count from local midnight, converted to UTC.
    midnight = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    counts = ctx.items.counts_by_topic(midnight.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%fZ"))
    return [{**t.model_dump(), "items_today": counts.get(t.id, 0)} for t in ctx.topics.list()]


@router.post("/topics", status_code=201)
def create_topic(request: Request, data: dict[str, Any]) -> Topic:
    return _ctx(request).topics.create(data)


@router.get("/topics/{topic_id}")
def get_topic(request: Request, topic_id: int) -> Topic:
    return _ctx(request).topics.get(topic_id)


@router.put("/topics/{topic_id}")
def update_topic(request: Request, topic_id: int, data: dict[str, Any]) -> Topic:
    return _ctx(request).topics.update(topic_id, data)


class ActiveBody(BaseModel):
    active: bool


@router.patch("/topics/{topic_id}/active")
def set_topic_active(request: Request, topic_id: int, body: ActiveBody) -> Topic:
    return _ctx(request).topics.set_active(topic_id, body.active)


@router.delete("/topics/{topic_id}", status_code=204)
def delete_topic(request: Request, topic_id: int) -> None:
    _ctx(request).topics.delete(topic_id)


@router.get("/topics/{topic_id}/items")
def topic_items(request: Request, topic_id: int, limit: int = 100) -> list[dict[str, Any]]:
    ctx = _ctx(request)
    ctx.topics.get(topic_id)  # 404 for unknown topics
    return ctx.items.for_topic(topic_id, min(max(limit, 1), 500))
