"""Hot score (0-100) for a theme, explainable component by component.

Components, each in 0..1:
- volume:    today's items vs the average of the previous days observed (up to 7);
             a ratio of 8x or more counts as full marks.
- growth:    change vs yesterday; tripling counts as full marks.
- diversity: number of distinct sources (news, YouTube, Reddit, feeds, trends); 4+ is full.
- size:      absolute number of items today (log scale); 30+ is full.
Without history (a brand-new topic or term) volume and growth are neutral (0.5)
and the trend is "new".
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

Trend = Literal["up", "down", "flat", "new"]

WEIGHTS = {"volume": 0.35, "growth": 0.2, "diversity": 0.2, "size": 0.25}


@dataclass(frozen=True)
class ScoreInput:
    today: int
    previous_days: list[int]  # counts for the previous observed days, most recent first
    sources: int


def _clip(value: float) -> float:
    return max(0.0, min(1.0, value))


def hot_score(data: ScoreInput) -> tuple[int, Trend, dict[str, Any]]:
    size = _clip(math.log2(data.today + 1) / math.log2(31))
    diversity = _clip(data.sources / 4)

    if not data.previous_days:
        volume = growth = 0.5
        average = None
        yesterday = None
        trend: Trend = "new"
    else:
        average = sum(data.previous_days) / len(data.previous_days)
        yesterday = data.previous_days[0]
        ratio = (data.today + 1) / (average + 1)
        volume = _clip(math.log2(ratio) / 3)
        growth = _clip((data.today - yesterday) / (yesterday + 1) / 3)
        if (yesterday == 0 and data.today > 0) or data.today > yesterday * 1.1:
            trend = "up"
        elif data.today < yesterday * 0.9:
            trend = "down"
        else:
            trend = "flat"

    components = {"volume": volume, "growth": growth, "diversity": diversity, "size": size}
    score = round(100 * sum(WEIGHTS[k] * v for k, v in components.items()))
    details = {
        "today": data.today,
        "yesterday": yesterday,
        "average": round(average, 2) if average is not None else None,
        "days_observed": len(data.previous_days),
        "sources": data.sources,
        "components": {k: round(v, 3) for k, v in components.items()},
    }
    return score, trend, details
