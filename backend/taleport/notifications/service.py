"""Notifications: the in-app bell (stored, live over SSE) plus a Windows notification.

The backend stores a `kind` and `params`; the UI translates them like errors. The Windows
notification text comes from the backend catalog (`resources/i18n`), because it is shown
while the window may be closed. A `dedupe_key` keeps repeated events (the same source
failing on every scan of the day) to one notification.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from taleport.core.events import EventBus
from taleport.core.i18n import tr
from taleport.core.settings import AppSettings, SettingsStore
from taleport.db.database import Database
from taleport.notifications.rules import detect_spikes

log = logging.getLogger(__name__)

Toaster = Callable[[str, str], None]  # (title, message)


class NotificationService:
    def __init__(self, db: Database, bus: EventBus, settings: SettingsStore) -> None:
        self._db = db
        self._bus = bus
        self._settings = settings
        self.toaster: Toaster | None = None  # set by the desktop shell (tray icon)

    # -- writing -------------------------------------------------------------------------

    def notify(
        self,
        kind: str,
        params: dict[str, Any] | None = None,
        *,
        link: str | None = None,
        dedupe_key: str | None = None,
        toast: bool = True,
    ) -> int | None:
        """Store and announce a notification; None if `dedupe_key` was already used."""
        params = params or {}
        with self._db.connect() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO notifications (kind, params, link, dedupe_key) "
                "VALUES (?, ?, ?, ?)",
                (kind, json.dumps(params, ensure_ascii=False), link, dedupe_key),
            )
            if not cursor.rowcount:
                return None
            notification_id = int(cursor.lastrowid or 0)
        self._bus.publish("notification", {"id": notification_id, "kind": kind})
        settings = self._settings.get()
        if toast and settings.notify_windows and self.toaster is not None:
            title, message = self.toast_text(settings.language, kind, params)
            try:
                self.toaster(title, message)
            except Exception:  # a failed Windows notification must not break a scan
                log.warning("Windows notification failed", exc_info=True)
        return notification_id

    @staticmethod
    def toast_text(language: str, kind: str, params: dict[str, Any]) -> tuple[str, str]:
        shown = dict(params)
        if "source" in shown:
            shown["source"] = tr(language, f"source.{shown['source']}")
        return tr(language, f"notify.{kind}.title"), tr(language, f"notify.{kind}.body", **shown)

    # -- events --------------------------------------------------------------------------

    def after_scan(self, summary: dict[str, Any], day: date) -> None:
        """Scan completed/recovered, failing sources, sudden spikes on a topic."""
        status, trigger = summary["status"], summary["trigger"]
        if status in ("completed", "partial"):
            self.notify(
                "scan_recovered" if trigger == "catchup" else "scan_completed",
                {"new": summary["items_new"], "found": summary["items_found"]},
                link="/today",
                toast=trigger != "manual",  # a manual scan is watched in the window
            )
        failing: dict[str, str] = {}
        for cell in summary["cells"]:
            if cell["state"] == "error":
                failing.setdefault(cell["source"], cell.get("code") or "internal")
        for source, code in failing.items():
            self.notify(
                "source_failing",
                {"source": source, "code": code},
                dedupe_key=f"source:{source}:{day.isoformat()}",
            )
        topic_ids = [t["id"] for t in summary["topics"]]
        with self._db.connect() as conn:
            spikes = detect_spikes(conn, day, topic_ids)
        for spike in spikes:
            link = f"/themes/{spike['theme_id']}" if spike["theme_id"] else "/today"
            self.notify(
                "spike",
                {k: spike[k] for k in ("topic", "today", "average", "theme")},
                link=link,
                dedupe_key=f"spike:{spike['topic_id']}:{day.isoformat()}",
            )

    def check_spend(self, month_total: float, settings: AppSettings, now: datetime) -> None:
        cap = settings.spend_cap_usd
        if not cap:
            return
        month = now.strftime("%Y-%m")
        params = {"total": round(month_total, 2), "cap": round(cap, 2)}
        if month_total >= cap:
            self.notify("spend_reached", params, link="/settings", dedupe_key=f"spend:{month}:cap")
        elif month_total >= cap * settings.spend_warn_percent / 100:
            self.notify("spend_near", params, link="/settings", dedupe_key=f"spend:{month}:near")

    # -- reading -------------------------------------------------------------------------

    @staticmethod
    def _to_dict(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["params"] = json.loads(row["params"])
        data["read"] = bool(row["read"])
        data.pop("dedupe_key", None)
        return data

    def list(self, limit: int = 30) -> dict[str, Any]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM notifications ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            unread = conn.execute("SELECT COUNT(*) FROM notifications WHERE read = 0").fetchone()
        return {"unread": int(unread[0]), "rows": [self._to_dict(r) for r in rows]}

    def mark_read(self, ids: list[int] | None = None) -> None:
        with self._db.connect() as conn:
            if ids is None:
                conn.execute("UPDATE notifications SET read = 1 WHERE read = 0")
            elif ids:
                marks = ",".join("?" * len(ids))
                conn.execute(f"UPDATE notifications SET read = 1 WHERE id IN ({marks})", ids)
        self._bus.publish("notification", {"read": True})

    def clear(self) -> None:
        with self._db.connect() as conn:
            conn.execute("DELETE FROM notifications WHERE read = 1")
        self._bus.publish("notification", {"read": True})
