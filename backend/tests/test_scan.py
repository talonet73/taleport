from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from taleport.api.context import AppContext
from taleport.collectors.base import CollectedItem, CollectorError, SourceSkipped
from taleport.core.errors import AppError
from taleport.scan.scheduler import ScanScheduler, last_slot
from tests.conftest import FakeCollector, topic_payload


def _items(n: int, prefix: str = "story") -> list[CollectedItem]:
    return [
        CollectedItem(
            source="news",
            url=f"https://n.com/{prefix}{i}",
            title=f"Unique {prefix} headline number {i} here",
        )
        for i in range(n)
    ]


def test_scan_runs_every_source_and_isolates_failures(ctx: AppContext, collectors: list) -> None:
    good = FakeCollector("news", _items(3))
    broken = FakeCollector("reddit", error=CollectorError("reddit.blocked"))
    skipped = FakeCollector("youtube", error=SourceSkipped("youtube.no_key"))
    collectors.extend([good, broken, skipped])
    t1 = ctx.topics.create(topic_payload(name="A"))
    t2 = ctx.topics.create(topic_payload(name="B"))
    ctx.topics.create(topic_payload(name="Paused", active=False))

    scan_id = ctx.scans.start("manual")
    ctx.scans.wait(5)

    snapshot = ctx.scans.current()
    assert snapshot and snapshot["status"] == "partial"
    assert good.calls == [t1.id, t2.id]  # paused topic not scanned
    states = {(c["source"], c["topic_id"]): (c["state"], c["code"]) for c in snapshot["cells"]}
    assert states[("news", t1.id)] == ("done", None)
    assert states[("reddit", t1.id)] == ("error", "reddit.blocked")
    assert states[("youtube", t2.id)] == ("skipped", "youtube.no_key")

    row = ctx.scans.history(1)[0]
    assert row["id"] == scan_id and row["status"] == "partial"
    assert row["items_new"] == 3 and row["items_found"] == 6 and row["errors"] == 2
    assert {log["code"] for log in ctx.logs.recent()} >= {
        "reddit.blocked",
        "scan.finished_with_errors",
    }
    assert len(ctx.items.for_topic(t2.id)) == 3


def test_scan_single_topic_and_guards(ctx: AppContext, collectors: list) -> None:
    with pytest.raises(AppError) as info:
        ctx.scans.start("manual")
    assert info.value.code == "scan.no_topics"

    collectors.append(FakeCollector("news", _items(1)))
    t1 = ctx.topics.create(topic_payload(name="A"))
    ctx.topics.create(topic_payload(name="B"))
    ctx.scans.start("manual", t1.id)
    ctx.scans.wait(5)
    assert collectors[0].calls == [t1.id]
    assert ctx.scans.current()["status"] == "completed"


def test_has_full_scan_since_and_interrupted_scans(ctx: AppContext, collectors: list) -> None:
    collectors.append(FakeCollector("news"))
    topic = ctx.topics.create(topic_payload())
    before = (datetime.now(UTC) - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%fZ")

    ctx.scans.start("manual", topic.id)  # single-topic scans don't count as the daily scan
    ctx.scans.wait(5)
    assert not ctx.scans.has_full_scan_since(before)

    ctx.scans.start("manual")
    ctx.scans.wait(5)
    assert ctx.scans.has_full_scan_since(before)

    with ctx.db.connect() as conn:
        conn.execute("INSERT INTO scans (trigger, status) VALUES ('scheduled', 'running')")
    ctx.scans.mark_interrupted()
    assert all(r["status"] != "running" for r in ctx.scans.history())


def test_last_slot() -> None:
    tz = datetime.now().astimezone().tzinfo
    morning = datetime(2026, 11, 2, 6, 0, tzinfo=tz)
    evening = datetime(2026, 11, 2, 20, 0, tzinfo=tz)
    assert last_slot(morning, "07:30") == datetime(2026, 11, 1, 7, 30, tzinfo=tz)
    assert last_slot(evening, "07:30") == datetime(2026, 11, 2, 7, 30, tzinfo=tz)


def test_catch_up_only_when_the_slot_was_missed(ctx: AppContext, collectors: list) -> None:
    collectors.append(FakeCollector("news"))
    ctx.topics.create(topic_payload())
    scheduler = ScanScheduler(ctx.scans)
    now = datetime.now().astimezone()
    slot = (now - timedelta(hours=1)).strftime("%H:%M")

    assert scheduler.catch_up_if_needed(slot, now) is True

    ctx.scans.start("scheduled")
    ctx.scans.wait(5)
    assert scheduler.catch_up_if_needed(slot, now) is False


def test_scan_api(client: TestClient, ctx: AppContext, collectors: list) -> None:
    collectors.append(FakeCollector("news", _items(2)))
    topic_id = client.post("/api/topics", json=topic_payload()).json()["id"]

    response = client.post("/api/scans", json={})
    assert response.status_code == 202
    ctx.scans.wait(5)
    assert client.get("/api/scans/current").json()["status"] == "completed"
    assert client.get("/api/scans").json()[0]["items_new"] == 2
    assert client.get(f"/api/topics/{topic_id}/items").json()[0]["source"] == "news"
    assert client.get("/api/topics").json()[0]["items_today"] == 2
    assert client.get("/api/status").json()["last_scan_at"]
    assert client.get("/api/quota/youtube").json()["limit"] == 10_000
