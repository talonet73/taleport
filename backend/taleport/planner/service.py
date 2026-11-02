"""Calendar of scheduled and published posts, and suggested posting times.

`drafts.scheduled_at` is a local date-time ("YYYY-MM-DDTHH:MM"); publication times are UTC
and are shown in local time. Suggested times: the defaults in `resources/posting_times.json`,
replaced by the user's own choice, plus a "learned" time from the results entered: the hour
whose posts had the most interactions on average.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from functools import cache
from pathlib import Path
from statistics import mean
from typing import Any

from taleport.core.errors import AppError
from taleport.core.settings import PLATFORMS, SettingsStore
from taleport.db.database import Database
from taleport.generator.service import GeneratorService
from taleport.results.service import interactions

_DEFAULTS = Path(__file__).resolve().parent.parent / "resources" / "posting_times.json"
LEARN_MIN_POSTS = 3  # results on the platform before learning a time
LEARN_MIN_PER_HOUR = 2  # posts in the winning hour
MAX_RANGE_DAYS = 62
MAX_UNSCHEDULED = 60


@cache
def default_times() -> dict[str, str]:
    data = json.loads(_DEFAULTS.read_text(encoding="utf-8"))
    return {p: data[p] for p in PLATFORMS}


def _local(utc_text: str) -> datetime:
    value = datetime.fromisoformat(utc_text.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone()


class PlannerService:
    def __init__(self, db: Database, settings: SettingsStore, generator: GeneratorService) -> None:
        self._db = db
        self._settings = settings
        self._generator = generator

    # -- posting times -------------------------------------------------------------------

    def _learned(self) -> dict[str, dict[str, Any]]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT d.platform, p.published_at, r.likes, r.comments, r.shares "
                "FROM post_results r JOIN drafts d ON d.id = r.draft_id "
                "JOIN publications p ON p.draft_id = d.id"
            ).fetchall()
        by_platform: dict[str, dict[int, list[int]]] = defaultdict(lambda: defaultdict(list))
        for row in rows:
            try:
                hour = _local(row["published_at"]).hour
            except ValueError:
                continue
            by_platform[row["platform"]][hour].append(interactions(row))
        learned = {}
        for platform, hours in by_platform.items():
            if sum(len(v) for v in hours.values()) < LEARN_MIN_POSTS:
                continue
            candidates = {h: v for h, v in hours.items() if len(v) >= LEARN_MIN_PER_HOUR}
            if not candidates:
                continue
            hour = max(candidates, key=lambda h: (mean(candidates[h]), -h))
            learned[platform] = {
                "time": f"{hour:02d}:00",
                "posts": len(candidates[hour]),
                "average": round(mean(candidates[hour]), 1),
            }
        return learned

    def posting_times(self) -> list[dict[str, Any]]:
        custom = self._settings.get().posting_times
        learned = self._learned()
        return [
            {
                "platform": p,
                "default": default_times()[p],
                "custom": custom.get(p),
                "time": custom.get(p) or default_times()[p],
                "learned": learned.get(p),
            }
            for p in PLATFORMS
        ]

    def time_for(self, platform: str) -> str:
        return self._settings.get().posting_times.get(platform) or default_times()[platform]

    # -- calendar ------------------------------------------------------------------------

    def calendar(self, start: date, end: date) -> dict[str, Any]:
        if end < start or (end - start).days > MAX_RANGE_DAYS:
            raise AppError("validation", fields=["start", "end"])
        entries = []
        with self._db.connect() as conn:
            scheduled = conn.execute(
                "SELECT id, platform, language, source_label, text, status, scheduled_at, "
                "topic_id FROM drafts WHERE status = 'scheduled' AND scheduled_at >= ? "
                "AND scheduled_at < ? ORDER BY scheduled_at",
                (start.isoformat(), (end + timedelta(days=1)).isoformat()),
            ).fetchall()
            for row in scheduled:
                day, _, clock = row["scheduled_at"].partition("T")
                entries.append(self._entry(row, day, clock[:5]))
            # Publication times are UTC: widen the query by a day and filter in local time.
            published = conn.execute(
                "SELECT d.id, d.platform, d.language, d.source_label, d.text, d.status, "
                "d.scheduled_at, d.topic_id, p.published_at, p.url FROM drafts d "
                "JOIN publications p ON p.draft_id = d.id "
                "WHERE p.published_at >= ? AND p.published_at < ?",
                ((start - timedelta(days=1)).isoformat(), (end + timedelta(days=2)).isoformat()),
            ).fetchall()
            for row in published:
                try:
                    when = _local(row["published_at"])
                except ValueError:
                    continue
                if start <= when.date() <= end:
                    entry = self._entry(row, when.date().isoformat(), when.strftime("%H:%M"))
                    entry["url"] = row["url"]
                    entries.append(entry)
            unscheduled = conn.execute(
                "SELECT id, platform, language, source_label, text, status, scheduled_at, "
                "topic_id FROM drafts WHERE status = 'draft' ORDER BY id DESC LIMIT ?",
                (MAX_UNSCHEDULED,),
            ).fetchall()
        entries.sort(key=lambda e: (e["day"], e["time"], e["id"]))
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "entries": entries,
            "unscheduled": [self._entry(r, None, None) for r in unscheduled],
            "posting_times": self.posting_times(),
        }

    @staticmethod
    def _entry(row: Any, day: str | None, clock: str | None) -> dict[str, Any]:
        return {
            "id": row["id"],
            "platform": row["platform"],
            "language": row["language"],
            "label": row["source_label"],
            "preview": row["text"][:160],
            "status": row["status"],
            "topic_id": row["topic_id"],
            "day": day,
            "time": clock,
        }

    def move(self, draft_id: int, day: date, clock: str | None = None) -> dict[str, Any]:
        """Drop a draft on a day: keeps its time if it had one, else the platform's time."""
        draft = self._generator.get(draft_id)
        if draft["status"] == "published":
            raise AppError("calendar.published")
        if clock is None:
            current = draft["scheduled_at"]
            clock = current.partition("T")[2][:5] if current else self.time_for(draft["platform"])
        try:
            datetime.strptime(clock, "%H:%M")
        except ValueError as exc:
            raise AppError("validation", fields=["time"]) from exc
        return self._generator.schedule(draft_id, f"{day.isoformat()}T{clock}")
