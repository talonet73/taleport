"""AI providers, connection tests and AI features."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from taleport.ai.providers.base import ProviderError
from taleport.ai.registry import PROVIDER_IDS, available_models, provider_status
from taleport.api.context import AppContext
from taleport.core import clipboard as system_clipboard
from taleport.core.errors import AppError

router = APIRouter()


def _ctx(request: Request) -> AppContext:
    return request.app.state.ctx


def _check_provider(provider_id: str) -> None:
    if provider_id not in PROVIDER_IDS:
        raise AppError("ai.unknown_provider", status=404, provider=provider_id)


@router.get("/ai/providers")
def providers(request: Request) -> dict[str, Any]:
    ctx = _ctx(request)
    settings = ctx.settings.get()
    return {
        "default": settings.default_ai,
        "chat_site": settings.chat_site,
        "providers": [provider_status(p, settings, ctx.secrets) for p in PROVIDER_IDS],
    }


@router.get("/ai/providers/{provider_id}/models")
def provider_models(request: Request, provider_id: str) -> list[str]:
    _check_provider(provider_id)
    ctx = _ctx(request)
    try:
        return available_models(provider_id, ctx.settings.get(), ctx.secrets)
    except ProviderError as exc:
        raise AppError(exc.code, status=502, **exc.params) from exc


@router.post("/ai/providers/{provider_id}/test")
def test_provider(request: Request, provider_id: str) -> dict[str, Any]:
    _check_provider(provider_id)
    return _ctx(request).ai.test_provider(provider_id)


class TopicSuggestionRequest(BaseModel):
    description: str = Field(max_length=2000)
    editions: list[str] = Field(default_factory=lambda: ["it-IT"])
    mode: str | None = None


class TopicSuggestionParse(BaseModel):
    text: str = Field(max_length=50_000)
    editions: list[str] = Field(default_factory=lambda: ["it-IT"])


@router.post("/ai/topic-suggestion")
def topic_suggestion(request: Request, body: TopicSuggestionRequest) -> dict[str, Any]:
    return _ctx(request).ai.suggest_topic(body.description, body.editions, body.mode)


@router.post("/ai/topic-suggestion/parse")
def topic_suggestion_parse(request: Request, body: TopicSuggestionParse) -> dict[str, Any]:
    return _ctx(request).ai.parse_topic_suggestion(body.text, body.editions)


class ThemeInsightsRequest(BaseModel):
    topic_id: int
    mode: str | None = None


class ThemeInsightsParse(BaseModel):
    topic_id: int
    text: str = Field(max_length=100_000)


@router.post("/ai/theme-insights")
def theme_insights(request: Request, body: ThemeInsightsRequest) -> dict[str, Any]:
    ctx = _ctx(request)
    result = ctx.ai.theme_insights(body.topic_id, body.mode)
    if "updated" in result:
        ctx.bus.publish("analysis.finished", {"ai": True})
    return result


@router.post("/ai/theme-insights/parse")
def theme_insights_parse(request: Request, body: ThemeInsightsParse) -> dict[str, Any]:
    ctx = _ctx(request)
    result = ctx.ai.parse_theme_insights(body.topic_id, body.text)
    ctx.bus.publish("analysis.finished", {"ai": True})
    return result


class XSearchRequest(BaseModel):
    theme_id: int | None = None
    topic_id: int | None = None
    mode: str = "chat"  # "chat" (grok.com, free plan) or "xai" (paid API)


class XSearchSave(BaseModel):
    theme_id: int | None = None
    topic_id: int | None = None
    text: str = Field(max_length=100_000)


@router.post("/ai/x-search")
def x_search(request: Request, body: XSearchRequest) -> dict[str, Any]:
    return _ctx(request).ai.x_search(body.theme_id, body.topic_id, body.mode)


@router.post("/ai/x-search/save")
def x_search_save(request: Request, body: XSearchSave) -> dict[str, Any]:
    return _ctx(request).ai.save_x_report(body.theme_id, body.topic_id, body.text)


@router.get("/ai/usage")
def usage(request: Request) -> dict[str, Any]:
    ctx = _ctx(request)
    settings = ctx.settings.get()
    return {
        "month_total_usd": ctx.usage.month_total(),
        "cap_usd": settings.spend_cap_usd,
        "warn_percent": settings.spend_warn_percent,
        "cap_reached": ctx.ai.cap_reached(settings),
        "by_provider": ctx.usage.month_by_provider(),
        "recent": ctx.usage.recent(30),
    }


class ClipboardBody(BaseModel):
    text: str = Field(max_length=200_000)


@router.post("/app/clipboard")
def clipboard(body: ClipboardBody) -> dict[str, bool]:
    return {"copied": system_clipboard.copy_text(body.text)}
