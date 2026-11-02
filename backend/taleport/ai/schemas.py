"""Schemas for structured AI answers. Everything is validated before use."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Lenient(BaseModel):
    # Models sometimes add harmless extra keys: ignore them instead of failing.
    model_config = ConfigDict(extra="ignore")


class ThemeInsight(_Lenient):
    id: int
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field("", max_length=1500)
    angle: str = Field("", max_length=800)
    same_as: int | None = None


class ThemeInsights(_Lenient):
    themes: list[ThemeInsight] = Field(min_length=1)


class SuggestedSource(_Lenient):
    kind: str
    value: str


class TopicSuggestion(_Lenient):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field("", max_length=2000)
    keywords: dict[str, list[str]] = Field(default_factory=dict)
    exclude: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    sources: list[SuggestedSource] = Field(default_factory=list)
    audience: str = Field("", max_length=1000)
    tone: str = Field("", max_length=500)
    platforms: list[str] = Field(default_factory=list)
