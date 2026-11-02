"""Daily scan scheduling with catch-up.

If the PC was off (or the app closed) at the scheduled time, the scan runs shortly after
the next start. APScheduler's coalescing and grace time cover sleep/hibernation while
the app keeps running.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from taleport.core.errors import AppError
from taleport.scan.service import ScanService, Trigger

log = logging.getLogger(__name__)

JOB_ID = "daily-scan"
CATCH_UP_DELAY = timedelta(seconds=20)


def last_slot(now: datetime, scan_time: str) -> datetime:
    """Most recent scheduled time at or before `now` (local, timezone-aware)."""
    hour, minute = (int(part) for part in scan_time.split(":"))
    slot = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return slot if slot <= now else slot - timedelta(days=1)


class ScanScheduler:
    def __init__(self, scans: ScanService) -> None:
        self._scans = scans
        self._scheduler = BackgroundScheduler(
            job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 3 * 3600}
        )

    def start(self, scan_time: str) -> None:
        self._scheduler.start()
        self.reschedule(scan_time)

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def reschedule(self, scan_time: str) -> None:
        hour, minute = (int(part) for part in scan_time.split(":"))
        self._scheduler.add_job(
            self._run,
            CronTrigger(hour=hour, minute=minute),
            args=["scheduled"],
            id=JOB_ID,
            replace_existing=True,
        )
        log.info("Daily scan scheduled at %s", scan_time)

    def next_run_at(self) -> datetime | None:
        job = self._scheduler.get_job(JOB_ID)
        return job.next_run_time if job else None

    def catch_up_if_needed(self, scan_time: str, now: datetime | None = None) -> bool:
        """Queue a catch-up scan when the last scheduled slot was missed."""
        now = now or datetime.now().astimezone()
        slot = last_slot(now, scan_time)
        if self._scans.has_full_scan_since(slot.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%fZ")):
            return False
        log.info("Missed the scan of %s: catching up", slot.isoformat())
        self._scheduler.add_job(
            self._run, "date", run_date=now + CATCH_UP_DELAY, args=["catchup"], id="catch-up",
            replace_existing=True,
        )  # fmt: skip
        return True

    def _run(self, trigger: Trigger) -> None:
        try:
            self._scans.start(trigger)
        except AppError as exc:
            # No active topics or a scan already running: nothing to do.
            log.info("Scheduled scan not started: %s", exc.code)
