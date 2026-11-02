"""'Already covered': themes similar to something the user published recently."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from taleport.collectors.text import normalize_title, title_tokens

COVERED_WINDOW_DAYS = 30
TITLE_SIMILARITY = 0.5


def published_themes(conn: sqlite3.Connection, topic_id: int) -> list[tuple[str, str]]:
    """(theme_key, theme_title) of drafts published for the topic in the window."""
    since = (datetime.now(UTC) - timedelta(days=COVERED_WINDOW_DAYS)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT DISTINCT d.theme_key, d.theme_title FROM drafts d "
        "JOIN publications p ON p.draft_id = d.id "
        "WHERE d.topic_id = ? AND p.published_at >= ? AND d.theme_key IS NOT NULL",
        (topic_id, since),
    ).fetchall()
    return [(r["theme_key"], r["theme_title"] or "") for r in rows]


def is_covered(key: str, title: str, published: list[tuple[str, str]]) -> bool:
    tokens = title_tokens(normalize_title(title)) | set(key.split())
    for pub_key, pub_title in published:
        if pub_key == key:
            return True
        other = title_tokens(normalize_title(pub_title)) | set(pub_key.split())
        if tokens and other and len(tokens & other) / len(tokens | other) >= TITLE_SIMILARITY:
            return True
    return False
