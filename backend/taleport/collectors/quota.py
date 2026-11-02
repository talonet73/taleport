"""Daily quota bookkeeping for quota-limited APIs (YouTube Data API v3)."""

from __future__ import annotations

import threading
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from taleport.collectors.base import CollectorError, utc_now
from taleport.db.database import Database

# YouTube quotas reset at midnight Pacific Time; the default project quota is 10,000 units.
YOUTUBE_SERVICE = "youtube"
YOUTUBE_DAILY_LIMIT = 10_000
_PACIFIC = ZoneInfo("America/Los_Angeles")


class QuotaTracker:
    def __init__(
        self, db: Database, service: str = YOUTUBE_SERVICE, limit: int = YOUTUBE_DAILY_LIMIT
    ):
        self._db = db
        self._service = service
        self.limit = limit
        self._lock = threading.Lock()

    @staticmethod
    def _now_pacific() -> datetime:
        return utc_now().astimezone(_PACIFIC)

    def today(self) -> str:
        return self._now_pacific().date().isoformat()

    def resets_at(self) -> str:
        tomorrow = self._now_pacific().date() + timedelta(days=1)
        return datetime.combine(tomorrow, time(0), _PACIFIC).isoformat()

    def used(self) -> int:
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT units FROM api_quota WHERE service = ? AND day = ?",
                (self._service, self.today()),
            ).fetchone()
        return row["units"] if row else 0

    def reserve(self, units: int) -> None:
        """Count units before a call; raises when the daily budget would be exceeded."""
        with self._lock:
            if self.used() + units > self.limit:
                raise CollectorError("youtube.quota_exhausted")
            self._add(units)

    def exhaust(self) -> None:
        """The API reported the quota as exceeded: align our counter."""
        with self._lock:
            self._add(max(0, self.limit - self.used()))

    def _add(self, units: int) -> None:
        with self._db.connect() as conn:
            conn.execute(
                "INSERT INTO api_quota (service, day, units) VALUES (?, ?, ?) "
                "ON CONFLICT(service, day) DO UPDATE SET units = units + excluded.units",
                (self._service, self.today(), units),
            )

    def status(self) -> dict:
        used = self.used()
        return {
            "used": used,
            "limit": self.limit,
            "remaining": max(0, self.limit - used),
            "resets_at": self.resets_at(),
        }
