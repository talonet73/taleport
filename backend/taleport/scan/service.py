"""Scan orchestration.

Each source runs in its own worker thread and walks through the topics, so a slow or
failing source (e.g. Reddit's pacing) never blocks the others. Progress is published per
(source, topic) cell on the event bus.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Literal

from taleport.collectors.base import Collector, CollectorError, SourceSkipped
from taleport.core.errors import AppError
from taleport.core.events import EventBus
from taleport.core.logs import LogStore
from taleport.db.database import Database
from taleport.scan.items import ItemRepository, filter_for_topic
from taleport.topics.models import Topic
from taleport.topics.service import TopicStore

log = logging.getLogger(__name__)

Trigger = Literal["manual", "scheduled", "catchup"]
CellState = Literal["pending", "running", "done", "skipped", "error"]


@dataclass
class Cell:
    state: CellState = "pending"
    found: int = 0
    new: int = 0
    code: str | None = None
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScanRun:
    scan_id: int
    trigger: Trigger
    topics: list[Topic]
    sources: list[str]
    cells: dict[tuple[str, int], Cell]
    cancel: threading.Event = field(default_factory=threading.Event)
    status: str = "running"

    def snapshot(self) -> dict[str, Any]:
        return {
            "scan_id": self.scan_id,
            "trigger": self.trigger,
            "status": self.status,
            "sources": self.sources,
            "topics": [{"id": t.id, "name": t.name} for t in self.topics],
            "cells": [{"source": s, "topic_id": t, **vars(c)} for (s, t), c in self.cells.items()],
        }


class ScanService:
    def __init__(
        self,
        db: Database,
        topics: TopicStore,
        items: ItemRepository,
        logs: LogStore,
        bus: EventBus,
        collectors_factory: Callable[[], list[Collector]],
    ) -> None:
        self._db = db
        self._topics = topics
        self._items = items
        self._logs = logs
        self._bus = bus
        self._factory = collectors_factory
        self._lock = threading.Lock()
        self._run: ScanRun | None = None
        self._thread: threading.Thread | None = None
        self.on_finished: list[Callable[[dict[str, Any]], None]] = []

    # -- control -----------------------------------------------------------------------

    def start(self, trigger: Trigger, topic_id: int | None = None) -> int:
        with self._lock:
            if self._run and self._run.status == "running":
                raise AppError("scan.running", status=409)
            topics = [self._topics.get(topic_id)] if topic_id else self._topics.active()
            if not topics:
                raise AppError("scan.no_topics")
            collectors = self._factory()
            with self._db.connect() as conn:
                cursor = conn.execute(
                    "INSERT INTO scans (trigger, topic_id, status) VALUES (?, ?, 'running')",
                    (trigger, topic_id),
                )
                scan_id = int(cursor.lastrowid or 0)
            sources = [c.source for c in collectors]
            run = ScanRun(
                scan_id=scan_id,
                trigger=trigger,
                topics=topics,
                sources=sources,
                cells={(s, t.id): Cell() for s in sources for t in topics},
            )
            self._run = run
            self._thread = threading.Thread(
                target=self._execute, args=(run, collectors), name=f"scan-{scan_id}", daemon=True
            )
            self._thread.start()
        log.info("Scan %d started (%s, %d topics)", scan_id, trigger, len(topics))
        self._bus.publish("scan.started", run.snapshot())
        return scan_id

    def cancel(self) -> None:
        run = self._run
        if run and run.status == "running":
            run.cancel.set()

    def wait(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout)

    def current(self) -> dict[str, Any] | None:
        return self._run.snapshot() if self._run else None

    def is_running(self) -> bool:
        return bool(self._run and self._run.status == "running")

    # -- execution ---------------------------------------------------------------------

    def _execute(self, run: ScanRun, collectors: list[Collector]) -> None:
        try:
            with ThreadPoolExecutor(max_workers=len(collectors) or 1) as pool:
                list(pool.map(lambda c: self._run_source(run, c), collectors))
        finally:
            self._finish(run)

    def _run_source(self, run: ScanRun, collector: Collector) -> None:
        for topic in run.topics:
            cell = run.cells[(collector.source, topic.id)]
            if run.cancel.is_set():
                cell.state = "skipped"
                cell.code = "scan.cancelled"
                continue
            cell.state = "running"
            self._progress(run, collector.source, topic.id)
            try:
                items = filter_for_topic(topic, collector.collect(topic))
                saved = self._items.save(items, topic.id, run.scan_id)
                cell.state, cell.found, cell.new = "done", saved.found, saved.new
            except SourceSkipped as exc:
                cell.state, cell.code, cell.params = "skipped", exc.code, exc.params
            except CollectorError as exc:
                cell.state, cell.code, cell.params = "error", exc.code, exc.params
                self._logs.add("warning", f"collector.{collector.source}", exc.code, exc.params)
            except Exception as exc:  # never let one source kill the scan
                log.exception("Collector %s failed on topic %d", collector.source, topic.id)
                cell.state, cell.code = "error", "internal"
                self._logs.add("error", f"collector.{collector.source}", "internal", {}, repr(exc))
            self._progress(run, collector.source, topic.id)

    def _progress(self, run: ScanRun, source: str, topic_id: int) -> None:
        cell = run.cells[(source, topic_id)]
        self._bus.publish(
            "scan.progress",
            {"scan_id": run.scan_id, "source": source, "topic_id": topic_id, **vars(cell)},
        )

    def _finish(self, run: ScanRun) -> None:
        cells = list(run.cells.values())
        errors = sum(c.state == "error" for c in cells)
        done = sum(c.state == "done" for c in cells)
        if run.cancel.is_set():
            run.status = "cancelled"
        elif errors and not done:
            run.status = "failed"
        elif errors:
            run.status = "partial"
        else:
            run.status = "completed"
        found = sum(c.found for c in cells)
        new = sum(c.new for c in cells)
        with self._db.connect() as conn:
            conn.execute(
                "UPDATE scans SET status = ?, finished_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), "
                "items_found = ?, items_new = ?, errors = ? WHERE id = ?",
                (run.status, found, new, errors, run.scan_id),
            )
        if errors:
            self._logs.add("warning", "scan", "scan.finished_with_errors", {"errors": errors})
        summary = {**run.snapshot(), "items_found": found, "items_new": new, "errors": errors}
        log.info(
            "Scan %d %s: %d found, %d new, %d errors", run.scan_id, run.status, found, new, errors
        )
        self._bus.publish("scan.finished", summary)
        for callback in self.on_finished:
            try:
                callback(summary)
            except Exception:
                log.exception("scan.finished callback failed")

    # -- history -----------------------------------------------------------------------

    def history(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._db.connect() as conn:
            rows = conn.execute("SELECT * FROM scans ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def last_finished_at(self) -> str | None:
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT finished_at FROM scans WHERE finished_at IS NOT NULL "
                "ORDER BY finished_at DESC LIMIT 1"
            ).fetchone()
        return row["finished_at"] if row else None

    def has_full_scan_since(self, since_iso_utc: str) -> bool:
        """A scan of all topics that ran (at least partly) after the given UTC time."""
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM scans WHERE topic_id IS NULL AND started_at >= ? "
                "AND status IN ('running', 'completed', 'partial') LIMIT 1",
                (since_iso_utc,),
            ).fetchone()
        return row is not None

    def mark_interrupted(self) -> None:
        """Scans left 'running' by a previous session that crashed or was closed mid-scan."""
        with self._db.connect() as conn:
            conn.execute(
                "UPDATE scans SET status = 'cancelled', "
                "finished_at = COALESCE(finished_at, started_at) WHERE status = 'running'"
            )
