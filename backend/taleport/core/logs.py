"""User-visible event/error log (the `logs` table), separate from the technical log file."""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
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

    def recent(self, limit: int = 100, level: Level | None = None) -> list[dict[str, Any]]:
        where, params = ("WHERE level = ?", [level]) if level else ("", [])
        with self._db.connect() as conn:
            rows = conn.execute(
                f"SELECT id, created_at, level, source, code, params FROM logs {where} "
                "ORDER BY id DESC LIMIT ?",
                (*params, limit),
            ).fetchall()
        return [{**dict(row), "params": json.loads(row["params"] or "{}")} for row in rows]

    def counts(self) -> dict[str, int]:
        with self._db.connect() as conn:
            rows = conn.execute("SELECT level, COUNT(*) AS n FROM logs GROUP BY level").fetchall()
        return {"info": 0, "warning": 0, "error": 0} | {r["level"]: r["n"] for r in rows}

    def clear(self) -> None:
        with self._db.connect() as conn:
            conn.execute("DELETE FROM logs")

    def export_text(self, header: dict[str, str], technical_log: str, limit: int = 2000) -> str:
        """Plain-text log for support: app info, the event log (with technical details) and
        the tail of the technical log file. No API keys are ever logged."""
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT created_at, level, source, code, params, details FROM logs "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        lines = ["TALeport", *(f"{k}: {v}" for k, v in header.items()), "", "== Events =="]
        for r in rows:
            line = f"{r['created_at']}  {r['level'].upper():7}  {r['source']}  {r['code']}"
            if r["params"] and r["params"] != "{}":
                line += f"  {r['params']}"
            lines.append(line)
            if r["details"]:
                lines.append(f"    {r['details']}")
        lines += ["", "== Technical log ==", technical_log]
        return "\n".join(lines)


def tail(path: Path, lines: int = 500) -> str:
    """Last lines of a text file ("" if it does not exist yet)."""
    if not path.exists():
        return ""
    with path.open(encoding="utf-8", errors="replace") as handle:
        return "".join(deque(handle, maxlen=lines))
