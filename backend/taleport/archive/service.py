"""Archive: every post and theme, with free-text search (SQLite FTS5) and filters.

The search box is never passed to FTS5 as a query: it is split into words, each quoted
and used as a prefix, all required ("intel artif" finds "intelligenza artificiale").
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from taleport.analysis.service import day_bounds_utc
from taleport.core.errors import AppError
from taleport.db.database import Database
from taleport.generator.service import GeneratorService

MAX_TERMS = 8
STATUSES = ("draft", "scheduled", "published")


def fts_query(text: str | None) -> str | None:
    words = re.findall(r"\w+", (text or "").lower())[:MAX_TERMS]
    return " ".join(f'"{w}"*' for w in words) or None


def _period(start: date | None, end: date | None, params: list, column: str) -> str:
    if start and end and end < start:
        raise AppError("validation", fields=["start", "end"])
    sql = ""
    if start:
        sql += f" AND {column} >= ?"
        params.append(day_bounds_utc(start)[0])
    if end:
        sql += f" AND {column} < ?"
        params.append(day_bounds_utc(end)[1])
    return sql


class ArchiveService:
    def __init__(self, db: Database) -> None:
        self._db = db

    def posts(
        self,
        q: str | None = None,
        status: str | None = None,
        platform: str | None = None,
        topic_id: int | None = None,
        start: date | None = None,
        end: date | None = None,
        limit: int = 30,
        offset: int = 0,
    ) -> dict[str, Any]:
        if status and status not in STATUSES:
            raise AppError("validation", fields=["status"])
        params: list = []
        joins = ""
        where = "1 = 1"
        match = fts_query(q)
        if match:
            joins = "JOIN drafts_fts f ON f.rowid = d.id"
            where += " AND drafts_fts MATCH ?"
            params.append(match)
        for column, value in (("d.status", status), ("d.platform", platform)):
            if value:
                where += f" AND {column} = ?"
                params.append(value)
        if topic_id:
            where += " AND d.topic_id = ?"
            params.append(topic_id)
        where += _period(start, end, params, "d.created_at")
        base = (
            f"FROM drafts d {joins} LEFT JOIN publications p ON p.draft_id = d.id "
            f"LEFT JOIN post_results r ON r.draft_id = d.id "
            f"LEFT JOIN topics t ON t.id = d.topic_id WHERE {where}"
        )
        with self._db.connect() as conn:
            total = conn.execute(f"SELECT COUNT(*) {base}", params).fetchone()[0]
            rows = conn.execute(
                f"SELECT d.*, t.name AS topic_name, p.published_at AS pub_at, p.url AS pub_url, "
                f"r.likes, r.comments, r.shares, r.views {base} "
                "ORDER BY d.id DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return {"total": int(total), "rows": [GeneratorService.list_row(r) for r in rows]}

    def themes(
        self,
        q: str | None = None,
        topic_id: int | None = None,
        start: date | None = None,
        end: date | None = None,
        limit: int = 30,
        offset: int = 0,
    ) -> dict[str, Any]:
        if start and end and end < start:
            raise AppError("validation", fields=["start", "end"])
        params: list = []
        joins = ""
        where = "1 = 1"
        match = fts_query(q)
        if match:
            joins = "JOIN themes_fts f ON f.rowid = th.id"
            where += " AND themes_fts MATCH ?"
            params.append(match)
        if topic_id:
            where += " AND th.topic_id = ?"
            params.append(topic_id)
        if start:
            where += " AND th.day >= ?"
            params.append(start.isoformat())
        if end:
            where += " AND th.day <= ?"
            params.append(end.isoformat())
        base = f"FROM themes th {joins} JOIN topics t ON t.id = th.topic_id WHERE {where}"
        with self._db.connect() as conn:
            total = conn.execute(f"SELECT COUNT(*) {base}", params).fetchone()[0]
            rows = conn.execute(
                "SELECT th.id, th.topic_id, t.name AS topic_name, th.day, th.title, th.summary, "
                "th.score, th.trend, th.item_count, th.related_terms, "
                "(SELECT COUNT(*) FROM drafts d WHERE d.theme_id = th.id) AS drafts, "
                "(SELECT COUNT(*) FROM drafts d JOIN publications p ON p.draft_id = d.id "
                f" WHERE d.theme_id = th.id) AS published {base} "
                "ORDER BY th.day DESC, th.score DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return {
            "total": int(total),
            "rows": [{**dict(r), "related_terms": json.loads(r["related_terms"])} for r in rows],
        }
