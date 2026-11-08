"""Validated shapes: video results (typed or read from screenshots) and the AI analysis."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PLATFORMS = ("instagram", "tiktok", "youtube", "facebook", "other")
Platform = Literal["instagram", "tiktok", "youtube", "facebook", "other"]
OwnerKind = Literal["client", "competitor"]


class _Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore")


class RetentionPoint(_Lenient):
    second: float = Field(ge=0, le=36_000)
    percent: float = Field(ge=0, le=100)


def _count(value: object) -> object:
    """'12,3K' / '1.2M' / '4.512' → numbers (screenshots and chat answers use these)."""
    if value is None or isinstance(value, int | float):
        return value
    text = str(value).strip().lower().replace(" ", "").replace(" ", "")
    if not text or text in {"-", "n/a", "null"}:
        return None
    factor = 1
    for suffix, mult in (("k", 1_000), ("mln", 1_000_000), ("m", 1_000_000), ("mila", 1_000)):
        if text.endswith(suffix):
            factor, text = mult, text[: -len(suffix)]
            break
    if factor > 1:
        text = text.replace(",", ".")
    elif "," in text and "." not in text and len(text.split(",")[-1]) == 3:
        text = text.replace(",", "")
    elif "." in text and len(text.split(".")[-1]) == 3 and text.count(".") >= 1 and "," not in text:
        text = text.replace(".", "")
    else:
        text = text.replace(",", ".")
    try:
        return round(float(text) * factor)
    except ValueError:
        return None


class VideoStats(_Lenient):
    """Results of one published video. Every field is optional: whatever the client sends."""

    platform: Platform | None = None
    views: int | None = Field(None, ge=0)
    reach: int | None = Field(None, ge=0)
    likes: int | None = Field(None, ge=0)
    comments: int | None = Field(None, ge=0)
    shares: int | None = Field(None, ge=0)
    saves: int | None = Field(None, ge=0)
    follows: int | None = Field(None, ge=0)
    avg_watch_seconds: float | None = Field(None, ge=0, le=36_000)
    duration: float | None = Field(None, ge=0, le=36_000)
    published: str | None = Field(None, max_length=40)
    retention: list[RetentionPoint] = Field(default_factory=list, max_length=60)
    notes: str = Field("", max_length=1000)

    @field_validator(
        "views", "reach", "likes", "comments", "shares", "saves", "follows", mode="before"
    )
    @classmethod
    def _numbers(cls, value: object) -> object:
        return _count(value)

    @field_validator("platform", mode="before")
    @classmethod
    def _platform(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip().lower()
            return value if value in PLATFORMS else "other"
        return value


class StatsReading(_Lenient):
    """What the AI read from the screenshots of one video."""

    stats: VideoStats


class Point(_Lenient):
    title: str = Field(min_length=1, max_length=200)
    detail: str = Field("", max_length=1500)
    videos: list[int] = Field(default_factory=list)


class CompetitorInsight(_Lenient):
    name: str = Field(min_length=1, max_length=120)
    what_works: str = Field("", max_length=1500)
    weak_spots: str = Field("", max_length=1500)
    to_borrow: str = Field("", max_length=1500)


class Recommendation(_Lenient):
    action: str = Field(min_length=1, max_length=400)
    why: str = Field("", max_length=1200)
    priority: Literal["high", "medium", "low"] = "medium"

    @field_validator("priority", mode="before")
    @classmethod
    def _priority(cls, value: object) -> object:
        mapping = {"alta": "high", "media": "medium", "bassa": "low", "baja": "low"}
        if isinstance(value, str):
            value = mapping.get(value.strip().lower(), value.strip().lower())
            return value if value in ("high", "medium", "low") else "medium"
        return value


class VideoVerdict(_Lenient):
    id: int
    verdict: str = Field("", max_length=800)
    hook: str = Field("", max_length=800)
    drop_off: str = Field("", max_length=800)
    fix: str = Field("", max_length=800)


class VideoAnalysis(_Lenient):
    summary: str = Field(min_length=1, max_length=3000)
    strengths: list[Point] = Field(default_factory=list, max_length=12)
    weaknesses: list[Point] = Field(default_factory=list, max_length=12)
    competitors: list[CompetitorInsight] = Field(default_factory=list, max_length=12)
    recommendations: list[Recommendation] = Field(default_factory=list, max_length=15)
    videos: list[VideoVerdict] = Field(default_factory=list, max_length=60)
    ideas: list[str] = Field(default_factory=list, max_length=15)
