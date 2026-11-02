"""Update check: compares this version with the latest release published at `update_url`.

Accepted answers:
- the GitHub Releases API ("https://api.github.com/repos/OWNER/taleport/releases/latest"):
  `tag_name`, `html_url`, `body`, `assets[].browser_download_url`;
- a plain JSON file: {"version": "0.2.0", "url": "https://…", "notes": "…"}.
The app never downloads or runs anything by itself: it offers to open the release page.
An automatic check runs at most once a day, at startup, when enabled in the settings.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from taleport import __version__
from taleport.collectors.http import HttpClient
from taleport.core.errors import AppError
from taleport.core.settings import SettingsStore
from taleport.db.database import Database
from taleport.notifications.service import NotificationService

log = logging.getLogger(__name__)

STATE_KEY = "_update_state"  # not an AppSettings field: never exported in backups
CHECK_EVERY = timedelta(days=1)
MAX_NOTES = 4000


def parse_version(text: str) -> tuple[int, ...]:
    """'v1.2.10' → (1, 2, 10); anything after the numbers (e.g. '-beta') is ignored."""
    numbers = re.findall(r"\d+", text.split("-")[0].split("+")[0])
    if not numbers:
        raise ValueError(text)
    return tuple(int(n) for n in numbers[:3]) + (0,) * (3 - min(len(numbers), 3))


def read_release(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("not an object")
    if "tag_name" in data:  # GitHub Releases API
        installer = next(
            (
                a.get("browser_download_url")
                for a in data.get("assets", []) or []
                if str(a.get("name", "")).lower().endswith(".exe")
            ),
            None,
        )
        version, url, notes = data["tag_name"], data.get("html_url"), data.get("body") or ""
    else:
        version, url, notes, installer = (
            data["version"], data.get("url"), data.get("notes") or "", None,
        )  # fmt: skip
    if not url or not str(url).startswith("https://"):
        raise ValueError("missing page url")
    return {
        "version": str(version).lstrip("vV"),
        "url": url,
        "installer_url": installer if installer and installer.startswith("https://") else None,
        "notes": str(notes)[:MAX_NOTES],
    }


class UpdateService:
    def __init__(
        self,
        db: Database,
        settings: SettingsStore,
        http: HttpClient,
        notifications: NotificationService,
        current: str = __version__,
    ) -> None:
        self._db = db
        self._settings = settings
        self._http = http
        self._notifications = notifications
        self.current = current

    def _state(self) -> dict[str, Any]:
        with self._db.connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (STATE_KEY,)).fetchone()
        return json.loads(row["value"]) if row else {}

    def _save_state(self, state: dict[str, Any]) -> None:
        with self._db.connect() as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (STATE_KEY, json.dumps(state)),
            )

    def status(self) -> dict[str, Any]:
        settings = self._settings.get()
        return {
            "current": self.current,
            "configured": bool(settings.update_url),
            "auto": settings.check_updates,
            **self._state(),
        }

    def check(self) -> dict[str, Any]:
        url = self._settings.get().update_url
        if not url:
            raise AppError("updates.not_configured")
        try:
            response = self._http.get(url)
        except Exception as exc:  # network errors after the client's retries
            raise AppError("updates.unreachable") from exc
        if response.status_code == 404:
            raise AppError("updates.no_release")
        if response.status_code >= 400:
            raise AppError("updates.unreachable")
        try:
            release = read_release(response.json())
            newer = parse_version(release["version"]) > parse_version(self.current)
        except (ValueError, KeyError, TypeError) as exc:
            raise AppError("updates.invalid_answer") from exc
        state = {
            "checked_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "latest": release,
            "available": newer,
        }
        self._save_state(state)
        if newer:
            self._notifications.notify(
                "update_available",
                {"version": release["version"], "current": self.current},
                link="/settings#updates",
                dedupe_key=f"update:{release['version']}",
            )
        return {"current": self.current, "configured": True, **state}

    def check_if_due(self, now: datetime | None = None) -> None:
        """Startup check: at most once a day, silent on errors (they go to the log file)."""
        settings = self._settings.get()
        if not (settings.check_updates and settings.update_url):
            return
        last = self._state().get("checked_at")
        now = now or datetime.now(UTC)
        if last and now - datetime.fromisoformat(last) < CHECK_EVERY:
            return
        try:
            self.check()
        except AppError as exc:
            log.info("Update check failed: %s", exc.code)
