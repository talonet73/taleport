"""User-visible event/error log (the `logs` table), separate from the technical log file."""

from __future__ import annotations

import json
from typing import Any, Literal

from taleport.db.database import Database

Level = Literal["info", "warning", "error"]


class LogStore:
    def __init__(self, db: Database) -> None:
        self._db = db

    def add(
        self,
        level: Level,
        source: str,
        code: str,
        params: dict[str, Any] | None = None,
        details: str | None = None,
    ) -> None:
        with self._db.connect() as conn:
            conn.execute(
                "INSERT INTO logs (level, source, code, params, details) VALUES (?, ?, ?, ?, ?)",
                (level, source, code, json.dumps(params or {}), details),
            )

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT id, created_at, level, source, code, params FROM logs "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{**dict(row), "params": json.loads(row["params"] or "{}")} for row in rows]
