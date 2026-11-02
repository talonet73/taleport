"""Results of published posts (entered by hand) and the priorities they suggest.

Interactions = likes + comments + shares (views are kept apart: not every platform shows
them). Priorities are always explained with the numbers behind them, e.g. "suggested
because posts on LinkedIn had more comments (12 on average)".
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from statistics import mean
from typing import Any

from taleport.collectors.text import normalize_title, title_tokens
from taleport.core.errors import AppError
from taleport.db.database import Database

METRICS = ("likes", "comments", "shares", "views")
INTERACTIONS = ("likes", "comments", "shares")
MIN_POSTS = 2  # results needed before a platform or theme can be suggested
LEAD_RATIO = 1.25  # how much better than the rest it must be
THEME_SIMILARITY = 0.5
MAX_VALUE = 1_000_000_000


def interactions(row: dict[str, Any] | sqlite3.Row) -> int:
    return sum(row[m] or 0 for m in INTERACTIONS)


def published_with_results(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Published drafts that have results."""
    return [
        dict(r)
        for r in conn.execute(
            "SELECT d.id, d.platform, d.topic_id, d.theme_key, d.theme_title, p.published_at, "
            "r.likes, r.comments, r.shares, r.views FROM post_results r "
            "JOIN drafts d ON d.id = r.draft_id JOIN publications p ON p.draft_id = d.id"
        )
    ]


def _averages(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    """Each metric averaged over the posts where it was entered (None if never)."""
    out: dict[str, float | None] = {}
    for m in METRICS:
        values = [r[m] for r in rows if r[m] is not None]
        out[m] = round(mean(values), 1) if values else None
    out["interactions"] = round(mean(interactions(r) for r in rows), 1)
    return out


def _lead_metric(group: list[dict[str, Any]], rest: list[dict[str, Any]]) -> tuple[str, float]:
    """The interaction metric where `group` beats `rest` the most, with its average."""
    best, best_ratio = "comments", 0.0
    for metric in INTERACTIONS:
        own = mean(r[metric] or 0 for r in group)
        other = mean(r[metric] or 0 for r in rest) if rest else 0
        ratio = own / other if other else (own and float("inf"))
        if ratio > best_ratio:
            best, best_ratio = metric, ratio
    return best, round(mean(r[best] or 0 for r in group), 1)


class ResultsService:
    def __init__(self, db: Database) -> None:
        self._db = db

    def save(self, draft_id: int, values: dict[str, int | None]) -> dict[str, Any] | None:
        clean = {m: values.get(m) for m in METRICS}
        if any(v is not None and not 0 <= v <= MAX_VALUE for v in clean.values()):
            raise AppError("validation", fields=[m for m, v in clean.items() if v is not None])
        with self._db.connect() as conn:
            row = conn.execute("SELECT status FROM drafts WHERE id = ?", (draft_id,)).fetchone()
            if row is None:
                raise AppError("drafts.not_found", status=404)
            if row["status"] != "published":
                raise AppError("results.not_published")
            if all(v is None for v in clean.values()):
                conn.execute("DELETE FROM post_results WHERE draft_id = ?", (draft_id,))
                return None
            conn.execute(
                "INSERT INTO post_results (draft_id, likes, comments, shares, views) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(draft_id) DO UPDATE SET "
                "likes = excluded.likes, comments = excluded.comments, "
                "shares = excluded.shares, views = excluded.views, "
                "updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')",
                (draft_id, *clean.values()),
            )
        return clean

    def summary(self) -> dict[str, Any]:
        """Averages per platform and the platform to favour (with the reason)."""
        with self._db.connect() as conn:
            rows = published_with_results(conn)
        by_platform: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_platform[row["platform"]].append(row)
        platforms = sorted(
            (
                {"platform": p, "posts": len(group), **_averages(group)}
                for p, group in by_platform.items()
            ),
            key=lambda r: -r["interactions"],
        )
        return {"posts": len(rows), "platforms": platforms, "reasons": self._reasons(by_platform)}

    @staticmethod
    def _reasons(by_platform: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
        eligible = {p: g for p, g in by_platform.items() if len(g) >= MIN_POSTS}
        if len(eligible) < 2:
            return []
        averages = {p: mean(interactions(r) for r in g) for p, g in eligible.items()}
        best = max(averages, key=lambda p: averages[p])
        rest = [r for p, g in eligible.items() if p != best for r in g]
        rest_avg = mean(interactions(r) for r in rest)
        if averages[best] < LEAD_RATIO * rest_avg:
            return []
        metric, value = _lead_metric(eligible[best], rest)
        return [
            {
                "code": "platform",
                "params": {"platform": best, "metric": metric, "value": value},
            }
        ]


class ThemePriority:
    """Explains why a theme deserves priority: similar published themes did well."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = [r for r in rows if r["theme_key"]]
        self._overall = mean(interactions(r) for r in rows) if rows else 0.0

    def reason(self, key: str, title: str) -> dict[str, Any] | None:
        if not self._rows:
            return None
        tokens = title_tokens(normalize_title(title)) | set(key.split())
        similar = []
        for row in self._rows:
            other = title_tokens(normalize_title(row["theme_title"] or "")) | set(
                row["theme_key"].split()
            )
            same = row["theme_key"] == key
            if same or (
                tokens and other and len(tokens & other) / len(tokens | other) >= THEME_SIMILARITY
            ):
                similar.append(row)
        if not similar:
            return None
        similar_avg = mean(interactions(r) for r in similar)
        if not similar_avg or similar_avg < LEAD_RATIO * self._overall:
            return None
        rest = [r for r in self._rows if r not in similar]
        metric, value = _lead_metric(similar, rest)
        best = max(similar, key=interactions)
        return {
            "code": "theme",
            "params": {
                "theme": best["theme_title"] or best["theme_key"],
                "metric": metric,
                "value": value,
                "posts": len(similar),
            },
        }
