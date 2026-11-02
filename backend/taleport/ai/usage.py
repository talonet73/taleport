"""AI usage log and cost estimates (USD)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any

from taleport.ai.providers.base import Completion
from taleport.db.database import Database

_PRICING = Path(__file__).resolve().parent.parent / "resources" / "ai_pricing.json"


@cache
def _price_table() -> dict[str, tuple[float, float]]:
    data = json.loads(_PRICING.read_text(encoding="utf-8"))
    return {model: (float(p[0]), float(p[1])) for model, p in data["models"].items()}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    price = _price_table().get(model) or _price_table().get(model.split("/")[-1])
    if price is None:
        return None
    return (input_tokens * price[0] + output_tokens * price[1]) / 1_000_000


class UsageStore:
    def __init__(self, db: Database) -> None:
        self._db = db

    def record(self, provider: str, feature: str, completion: Completion, *, paid: bool) -> None:
        if not paid:
            cost, source = 0.0, "free"
        elif completion.cost_usd is not None:
            cost, source = completion.cost_usd, "provider"
        else:
            cost = estimate_cost(
                completion.model, completion.input_tokens, completion.output_tokens
            )
            source = "estimate" if cost is not None else "unknown"
        with self._db.connect() as conn:
            conn.execute(
                "INSERT INTO ai_usage (provider, model, feature, input_tokens, output_tokens, "
                "cost_usd, cost_source) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    provider,
                    completion.model,
                    feature,
                    completion.input_tokens,
                    completion.output_tokens,
                    cost,
                    source,
                ),
            )

    @staticmethod
    def _month_start(now: datetime | None) -> str:
        # created_at is UTC: count from local midnight of the 1st, converted to UTC.
        now = now or datetime.now().astimezone()
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    def month_total(self, now: datetime | None = None) -> float:
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0) FROM ai_usage WHERE created_at >= ?",
                (self._month_start(now),),
            ).fetchone()
        return float(row[0])

    def month_by_provider(self, now: datetime | None = None) -> list[dict[str, Any]]:
        """This month's calls and cost per provider (calls with an unknown price counted)."""
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT provider, COUNT(*) AS calls, COALESCE(SUM(cost_usd), 0) AS cost_usd, "
                "SUM(cost_source = 'unknown') AS unknown FROM ai_usage WHERE created_at >= ? "
                "GROUP BY provider ORDER BY cost_usd DESC, calls DESC",
                (self._month_start(now),),
            ).fetchall()
        return [dict(r) for r in rows]

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM ai_usage ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
