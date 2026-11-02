"""Storing collected items with de-duplication.

An item is a duplicate when it has the same canonical URL, or when its normalized title is
identical or nearly identical (word Jaccard >= 0.8) to an item seen in the last few days.
Duplicates are not stored again: the existing item is linked to the topic instead.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from taleport.collectors.base import CollectedItem, utc_now
from taleport.collectors.text import (
    MIN_TOKENS_FOR_FUZZY,
    canonical_url,
    matches_any,
    near_duplicate,
    normalize_title,
    title_tokens,
)
from taleport.db.database import Database
from taleport.topics.models import Topic

DUPLICATE_WINDOW = timedelta(days=3)


@dataclass
class SaveResult:
    found: int = 0
    new: int = 0


def filter_for_topic(topic: Topic, items: list[CollectedItem]) -> list[CollectedItem]:
    """Drop items mentioning an excluded word (applies to watched sources too)."""
    if not topic.exclude:
        return items
    return [i for i in items if not matches_any(f"{i.title} {i.excerpt}", topic.exclude)]


class ItemRepository:
    def __init__(self, db: Database) -> None:
        self._db = db
        # Collectors run in parallel; serializing saves keeps duplicate checks consistent.
        self._lock = threading.Lock()

    def save(self, items: list[CollectedItem], topic_id: int, scan_id: int | None) -> SaveResult:
        result = SaveResult(found=len(items))
        if not items:
            return result
        with self._lock, self._db.connect() as conn:
            recent = self._recent_titles(conn)
            for item in items:
                item_id, is_new = self._upsert(conn, item, recent)
                conn.execute(
                    "INSERT OR IGNORE INTO item_topics (item_id, topic_id, scan_id) "
                    "VALUES (?, ?, ?)",
                    (item_id, topic_id, scan_id),
                )
                result.new += int(is_new)
        return result

    @staticmethod
    def _recent_titles(conn: sqlite3.Connection) -> list[tuple[int, str, frozenset[str]]]:
        since = (utc_now() - DUPLICATE_WINDOW).strftime("%Y-%m-%dT%H:%M:%fZ")
        rows = conn.execute(
            "SELECT id, title_key FROM items WHERE last_seen_at >= ?", (since,)
        ).fetchall()
        return [(r["id"], r["title_key"], title_tokens(r["title_key"])) for r in rows]

    @staticmethod
    def _upsert(
        conn: sqlite3.Connection,
        item: CollectedItem,
        recent: list[tuple[int, str, frozenset[str]]],
    ) -> tuple[int, bool]:
        canon = canonical_url(item.url)
        key = normalize_title(item.title, item.publisher)
        now = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"

        row = conn.execute(
            "SELECT id, extra FROM items WHERE canonical_url = ?", (canon,)
        ).fetchone()
        if row:
            extra = {**json.loads(row["extra"]), **item.extra}
            conn.execute(
                f"UPDATE items SET last_seen_at = {now}, "
                "metrics = CASE WHEN ? = '{}' THEN metrics ELSE ? END, extra = ? WHERE id = ?",
                (_dump(item.metrics), _dump(item.metrics), _dump(extra), row["id"]),
            )
            return row["id"], False

        # Short titles never match fuzzily, but the same title *and* excerpt (a post
        # cross-posted to several subreddits, a syndicated story) is the same item.
        if item.excerpt:
            same = conn.execute(
                "SELECT id FROM items WHERE title_key = ? AND excerpt = ? LIMIT 1",
                (key, item.excerpt),
            ).fetchone()
            if same:
                conn.execute(f"UPDATE items SET last_seen_at = {now} WHERE id = ?", (same["id"],))
                return same["id"], False

        tokens = title_tokens(key)
        if len(tokens) >= MIN_TOKENS_FOR_FUZZY:
            for existing_id, existing_key, existing_tokens in recent:
                if existing_key == key or near_duplicate(tokens, existing_tokens):
                    conn.execute(
                        f"UPDATE items SET last_seen_at = {now} WHERE id = ?", (existing_id,)
                    )
                    return existing_id, False

        cursor = conn.execute(
            "INSERT INTO items (source, url, canonical_url, title, title_key, excerpt, language, "
            "publisher, published_at, metrics, extra) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                item.source,
                item.url,
                canon,
                item.title,
                key,
                item.excerpt,
                item.language,
                item.publisher,
                item.published_at,
                _dump(item.metrics),
                _dump(item.extra),
            ),
        )
        item_id = int(cursor.lastrowid or 0)
        recent.append((item_id, key, tokens))
        return item_id, True

    def for_topic(self, topic_id: int, limit: int = 100) -> list[dict[str, Any]]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT i.id, i.source, i.url, i.title, i.excerpt, i.language, i.publisher, "
                "i.published_at, i.metrics, i.first_seen_at, t.linked_at FROM items i "
                "JOIN item_topics t ON t.item_id = i.id WHERE t.topic_id = ? "
                "ORDER BY t.linked_at DESC, i.id DESC LIMIT ?",
                (topic_id, limit),
            ).fetchall()
        return [{**dict(r), "metrics": json.loads(r["metrics"])} for r in rows]

    def counts_by_topic(self, since_iso: str) -> dict[int, int]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT topic_id, COUNT(*) AS n FROM item_topics WHERE linked_at >= ? "
                "GROUP BY topic_id",
                (since_iso,),
            ).fetchall()
        return {r["topic_id"]: r["n"] for r in rows}


def _dump(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
