"""'Ask' plans: a validated list of calls to the closed set of analysis functions.

The AI only produces this JSON. Anything outside the schema (unknown function, extra
arguments, SQL, too many steps, absurd limits) is rejected before running.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from taleport.ask.scope import Filters, Period

MAX_STEPS = 4


class _Step(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: Period = Field(default_factory=Period)
    filters: Filters = Field(default_factory=Filters)


class TopKeywords(_Step):
    function: Literal["top_keywords"]
    kind: Literal["keyword", "hashtag"] = "keyword"
    limit: int = Field(20, ge=1, le=50)


class EmergingKeywords(_Step):
    function: Literal["emerging_keywords"]
    limit: int = Field(10, ge=1, le=30)


class TopicTrend(_Step):
    function: Literal["topic_trend"]
    terms: list[Annotated[str, Field(max_length=60)]] = Field(default_factory=list, max_length=8)
    limit: int = Field(5, ge=1, le=8)


class ComparePeriods(BaseModel):
    model_config = ConfigDict(extra="forbid")

    function: Literal["compare_periods"]
    period_a: Period
    period_b: Period
    filters: Filters = Field(default_factory=Filters)
    kind: Literal["keyword", "hashtag"] = "keyword"
    limit: int = Field(15, ge=1, le=30)


class CompareLanguages(_Step):
    function: Literal["compare_languages"]
    limit: int = Field(5, ge=1, le=15)


class CompareSources(_Step):
    function: Literal["compare_sources"]
    limit: int = Field(5, ge=1, le=15)


class TopThemes(_Step):
    function: Literal["top_themes"]
    limit: int = Field(10, ge=1, le=30)


class PostPerformance(_Step):
    function: Literal["post_performance"]


Step = Annotated[
    TopKeywords
    | EmergingKeywords
    | TopicTrend
    | ComparePeriods
    | CompareLanguages
    | CompareSources
    | TopThemes
    | PostPerformance,
    Field(discriminator="function"),
]


class AskPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")  # tolerate a stray "explanation" key

    title: str = Field("", max_length=160)
    steps: list[Step] = Field(min_length=1, max_length=MAX_STEPS)


# Ready-made questions: run without any AI. Labels are translated in the UI by id.
PRESETS: dict[str, dict] = {
    "trending_week": {"steps": [
        {"function": "top_keywords", "period": {"preset": "last_7_days"}, "limit": 15},
        {"function": "topic_trend", "period": {"preset": "last_7_days"}},
    ]},
    "emerging": {"steps": [{"function": "emerging_keywords", "period": {"preset": "last_7_days"}}]},
    "hashtags_month": {"steps": [
        {"function": "top_keywords", "kind": "hashtag", "period": {"preset": "last_30_days"}},
    ]},
    "languages_month": {"steps": [
        {"function": "compare_languages", "period": {"preset": "last_30_days"}},
    ]},
    "hot_themes_week": {"steps": [{"function": "top_themes", "period": {"preset": "last_7_days"}}]},
    "this_vs_last_week": {"steps": [{
        "function": "compare_periods",
        "period_a": {"preset": "last_week"}, "period_b": {"preset": "this_week"},
    }]},
    "posts_month": {"steps": [
        {"function": "post_performance", "period": {"preset": "last_30_days"}},
    ]},
}  # fmt: skip
