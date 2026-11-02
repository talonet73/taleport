"""When something deserves a notification.

Spike: a topic collects today at least SPIKE_RATIO times its daily average of the previous
week, and at least SPIKE_MIN_ITEMS items. Days without any item (app closed) are left out
of the average; with fewer than SPIKE_MIN_HISTORY such days there is no baseline yet.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any

from taleport.analysis.service import day_bounds_utc

SPIKE_RATIO = 2.0
SPIKE_MIN_ITEMS = 10
SPIKE_MIN_HISTORY = 3
SPIKE_WINDOW_DAYS = 7


def _items_on(conn: sqlite3.Connection, topic_id: int, day: date) -> int:
    start, end = day_bounds_utc(day)
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM item_topics WHERE topic_id = ? AND linked_at >= ? "
            "AND linked_at < ?",
            (topic_id, start, end),
        ).fetchone()[0]
    )


def detect_spikes(
    conn: sqlite3.Connection, day: date, topic_ids: list[int]
) -> list[dict[str, Any]]:
    spikes = []
    for topic_id in topic_ids:
        today = _items_on(conn, topic_id, day)
        if today < SPIKE_MIN_ITEMS:
            continue
        history = [
            n
            for back in range(1, SPIKE_WINDOW_DAYS + 1)
            if (n := _items_on(conn, topic_id, day - timedelta(days=back)))
        ]
        if len(history) < SPIKE_MIN_HISTORY:
            continue
        average = sum(history) / len(history)
        if today < SPIKE_RATIO * average:
            continue
        topic = conn.execute("SELECT name FROM topics WHERE id = ?", (topic_id,)).fetchone()
        theme = conn.execute(
            "SELECT id, title FROM themes WHERE topic_id = ? AND day = ? ORDER BY position LIMIT 1",
            (topic_id, day.isoformat()),
        ).fetchone()
        spikes.append(
            {
                "topic_id": topic_id,
                "topic": topic["name"] if topic else "",
                "today": today,
                "average": round(average, 1),
                "theme_id": theme["id"] if theme else None,
                "theme": theme["title"] if theme else "",
            }
        )
    return spikes
