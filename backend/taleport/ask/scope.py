"""Periods and filters shared by the analysis functions, Trends and 'Ask'."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from taleport.analysis.service import day_bounds_utc, today_local

MAX_SPAN_DAYS = 366
PeriodPreset = Literal[
    "today", "last_7_days", "last_30_days", "this_week", "last_week", "this_month", "custom"
]
LanguageCode = Literal["it", "en", "es"]
SourceCode = Literal["news", "rss", "youtube", "reddit", "trends", "x_grok"]


class Period(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset: PeriodPreset = "last_7_days"
    start: date | None = None
    end: date | None = None

    @model_validator(mode="after")
    def _custom_needs_dates(self) -> Period:
        if self.preset == "custom":
            if self.start is None or self.end is None:
                raise ValueError("custom period needs start and end")
            if self.end < self.start:
                raise ValueError("end before start")
            if (self.end - self.start).days >= MAX_SPAN_DAYS:
                raise ValueError("period too long")
        return self

    def resolve(self, today: date | None = None) -> tuple[date, date]:
        """Inclusive local dates."""
        today = today or today_local()
        match self.preset:
            case "today":
                return today, today
            case "last_7_days":
                return today - timedelta(days=6), today
            case "last_30_days":
                return today - timedelta(days=29), today
            case "this_week":
                return today - timedelta(days=today.weekday()), today
            case "last_week":
                monday = today - timedelta(days=today.weekday() + 7)
                return monday, monday + timedelta(days=6)
            case "this_month":
                return today.replace(day=1), today
        assert self.start and self.end
        return self.start, min(self.end, today)


class Filters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topics: list[int] | None = Field(None, max_length=10)
    languages: list[LanguageCode] | None = None
    sources: list[SourceCode] | None = None


@dataclass(frozen=True)
class Scope:
    """A resolved period plus filters, ready for SQL."""

    start: date
    end: date
    topics: tuple[int, ...] | None = None
    languages: tuple[str, ...] | None = None
    sources: tuple[str, ...] | None = None

    @classmethod
    def build(
        cls, period: Period, filters: Filters | None = None, today: date | None = None
    ) -> Scope:
        start, end = period.resolve(today)
        f = filters or Filters()
        return cls(
            start=start,
            end=end,
            topics=tuple(f.topics) if f.topics else None,
            languages=tuple(f.languages) if f.languages else None,
            sources=tuple(f.sources) if f.sources else None,
        )

    @property
    def days(self) -> list[date]:
        return [self.start + timedelta(days=i) for i in range((self.end - self.start).days + 1)]

    def previous(self) -> Scope:
        """The period of the same length right before this one."""
        length = (self.end - self.start).days + 1
        return Scope(
            start=self.start - timedelta(days=length),
            end=self.start - timedelta(days=1),
            topics=self.topics,
            languages=self.languages,
            sources=self.sources,
        )

    def utc_bounds(self) -> tuple[str, str]:
        return day_bounds_utc(self.start)[0], day_bounds_utc(self.end)[1]

    def to_dict(self) -> dict:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "topics": list(self.topics) if self.topics else None,
            "languages": list(self.languages) if self.languages else None,
            "sources": list(self.sources) if self.sources else None,
        }
