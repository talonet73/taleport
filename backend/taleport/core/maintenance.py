"""Automatic clean-up of old data (privacy: keep only what is still useful).

- Collected items not seen for `retention_months` (setting; 0 = keep forever). Their links
  to topics and themes go with them; drafts keep their own snapshot of the sources, and
  word statistics (`keyword_stats`) stay, so trends and the archive keep their history.
- Event log entries and read notifications older than `LOG_DAYS`.
Runs at startup and after every scan.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from taleport.db.database import Database

log = logging.getLogger(__name__)

LOG_DAYS = 90
_FMT = "%Y-%m-%dT%H:%M:%S.000Z"


def cutoff_for(months: int, now: datetime) -> datetime:
    return now - timedelta(days=round(months * 30.44))


def cleanup(db: Database, retention_months: int, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    removed = {"items": 0, "logs": 0, "notifications": 0}
    log_cutoff = (now - timedelta(days=LOG_DAYS)).strftime(_FMT)
    with db.connect() as conn:
        if retention_months:
            cutoff = cutoff_for(retention_months, now).strftime(_FMT)
            removed["items"] = conn.execute(
                "DELETE FROM items WHERE last_seen_at < ?", (cutoff,)
            ).rowcount
        removed["logs"] = conn.execute(
            "DELETE FROM logs WHERE created_at < ?", (log_cutoff,)
        ).rowcount
        removed["notifications"] = conn.execute(
            "DELETE FROM notifications WHERE read = 1 AND created_at < ?", (log_cutoff,)
        ).rowcount
    if any(removed.values()):
        log.info("Clean-up: %s", removed)
    return removed
