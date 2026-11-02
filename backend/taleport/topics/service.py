"""Topic persistence (max 10 topics)."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from pydantic import ValidationError

from taleport.core.errors import AppError
from taleport.db.database import Database
from taleport.topics.models import MAX_TOPICS, Topic, TopicData, WatchedSource

_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


def validate_topic(data: dict[str, Any]) -> TopicData:
    """Validate raw input into TopicData, raising user-facing AppErrors."""
    try:
        topic = TopicData.model_validate(data)
    except ValidationError as exc:
        fields = sorted({str(err["loc"][0]) for err in exc.errors() if err["loc"]})
        raise AppError("topics.invalid", fields=fields) from exc

    sources: list[WatchedSource] = []
    for source in topic.sources:
        try:
            sources.append(source.normalized())
        except ValueError as exc:
            raise AppError("topics.invalid_source", kind=source.kind, value=source.value) from exc
    topic.sources = list({(s.kind, s.value): s for s in sources}.values())

    if not any(topic.keywords_for(lang) for lang in topic.languages):
        raise AppError("topics.keywords_required")
    return topic


class TopicStore:
    def __init__(self, db: Database) -> None:
        self._db = db

    # -- reading -----------------------------------------------------------------

    def list(self) -> list[Topic]:
        with self._db.connect() as conn:
            rows = conn.execute("SELECT * FROM topics ORDER BY position, id").fetchall()
            return [self._load(conn, row) for row in rows]

    def active(self) -> list[Topic]:
        return [topic for topic in self.list() if topic.active]

    def get(self, topic_id: int) -> Topic:
        with self._db.connect() as conn:
            row = conn.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
            if row is None:
                raise AppError("topics.not_found", status=404)
            return self._load(conn, row)

    @staticmethod
    def _load(conn: sqlite3.Connection, row: sqlite3.Row) -> Topic:
        topic_id = row["id"]
        keywords: dict[str, list[str]] = {}
        exclude: list[str] = []
        hashtags: list[str] = []
        for kw in conn.execute(
            "SELECT kind, language, value FROM topic_keywords WHERE topic_id = ? ORDER BY id",
            (topic_id,),
        ):
            if kw["kind"] == "include":
                keywords.setdefault(kw["language"], []).append(kw["value"])
            elif kw["kind"] == "exclude":
                exclude.append(kw["value"])
            else:
                hashtags.append(kw["value"])
        sources = [
            {"kind": s["kind"], "value": s["value"]}
            for s in conn.execute(
                "SELECT kind, value FROM topic_sources WHERE topic_id = ? ORDER BY id", (topic_id,)
            )
        ]
        examples = [
            e["text"]
            for e in conn.execute(
                "SELECT text FROM style_examples WHERE topic_id = ? ORDER BY position", (topic_id,)
            )
        ]
        return Topic.model_validate(
            {
                "id": topic_id,
                "name": row["name"],
                "description": row["description"],
                "active": bool(row["active"]),
                "editions": json.loads(row["editions"]),
                "keywords": keywords,
                "exclude": exclude,
                "hashtags": hashtags,
                "sources": sources,
                "audience": row["audience"],
                "tone": row["tone"],
                "platforms": json.loads(row["platforms"]),
                "style_examples": examples,
                "position": row["position"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )

    # -- writing -----------------------------------------------------------------

    def create(self, data: dict[str, Any]) -> Topic:
        topic = validate_topic(data)
        with self._db.connect() as conn:
            count, max_pos = conn.execute(
                "SELECT COUNT(*), COALESCE(MAX(position), -1) FROM topics"
            ).fetchone()
            if count >= MAX_TOPICS:
                raise AppError("topics.limit", status=409, max=MAX_TOPICS)
            cursor = conn.execute(
                "INSERT INTO topics (name, description, active, editions, audience, tone, "
                "platforms, position) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    topic.name,
                    topic.description,
                    int(topic.active),
                    json.dumps(topic.editions),
                    topic.audience,
                    topic.tone,
                    json.dumps(topic.platforms),
                    max_pos + 1,
                ),
            )
            topic_id = int(cursor.lastrowid or 0)
            self._write_children(conn, topic_id, topic)
        return self.get(topic_id)

    def update(self, topic_id: int, data: dict[str, Any]) -> Topic:
        topic = validate_topic(data)
        with self._db.connect() as conn:
            cursor = conn.execute(
                f"UPDATE topics SET name = ?, description = ?, active = ?, editions = ?, "
                f"audience = ?, tone = ?, platforms = ?, updated_at = {_NOW} WHERE id = ?",
                (
                    topic.name,
                    topic.description,
                    int(topic.active),
                    json.dumps(topic.editions),
                    topic.audience,
                    topic.tone,
                    json.dumps(topic.platforms),
                    topic_id,
                ),
            )
            if cursor.rowcount == 0:
                raise AppError("topics.not_found", status=404)
            self._write_children(conn, topic_id, topic)
        return self.get(topic_id)

    def set_active(self, topic_id: int, active: bool) -> Topic:
        with self._db.connect() as conn:
            cursor = conn.execute(
                f"UPDATE topics SET active = ?, updated_at = {_NOW} WHERE id = ?",
                (int(active), topic_id),
            )
            if cursor.rowcount == 0:
                raise AppError("topics.not_found", status=404)
        return self.get(topic_id)

    def delete(self, topic_id: int) -> None:
        with self._db.connect() as conn:
            if conn.execute("DELETE FROM topics WHERE id = ?", (topic_id,)).rowcount == 0:
                raise AppError("topics.not_found", status=404)

    @staticmethod
    def _write_children(conn: sqlite3.Connection, topic_id: int, topic: TopicData) -> None:
        # Keep cached lookups (e.g. YouTube uploads playlist) for sources that did not change.
        resolved = {
            (r["kind"], r["value"]): r["resolved"]
            for r in conn.execute(
                "SELECT kind, value, resolved FROM topic_sources WHERE topic_id = ?", (topic_id,)
            )
        }
        for table in ("topic_keywords", "topic_sources", "style_examples"):
            conn.execute(f"DELETE FROM {table} WHERE topic_id = ?", (topic_id,))

        keyword_rows = [
            (topic_id, "include", lang, word)
            for lang, words in topic.keywords.items()
            for word in words
        ]
        keyword_rows += [(topic_id, "exclude", "any", word) for word in topic.exclude]
        keyword_rows += [(topic_id, "hashtag", "any", tag) for tag in topic.hashtags]
        conn.executemany(
            "INSERT INTO topic_keywords (topic_id, kind, language, value) VALUES (?, ?, ?, ?)",
            keyword_rows,
        )
        conn.executemany(
            "INSERT INTO topic_sources (topic_id, kind, value, resolved) VALUES (?, ?, ?, ?)",
            [(topic_id, s.kind, s.value, resolved.get((s.kind, s.value))) for s in topic.sources],
        )
        conn.executemany(
            "INSERT INTO style_examples (topic_id, position, text) VALUES (?, ?, ?)",
            [(topic_id, i, text) for i, text in enumerate(topic.style_examples)],
        )

    # -- cached source lookups -----------------------------------------------------

    def source_resolved(self, topic_id: int, kind: str, value: str) -> str | None:
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT resolved FROM topic_sources WHERE topic_id = ? AND kind = ? AND value = ?",
                (topic_id, kind, value),
            ).fetchone()
        return row["resolved"] if row else None

    def set_source_resolved(self, topic_id: int, kind: str, value: str, resolved: str) -> None:
        with self._db.connect() as conn:
            conn.execute(
                "UPDATE topic_sources SET resolved = ? "
                "WHERE topic_id = ? AND kind = ? AND value = ?",
                (resolved, topic_id, kind, value),
            )
