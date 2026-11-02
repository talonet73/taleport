"""Archive search, post results and priorities, calendar, notifications, spending cap."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient

from taleport.ai.providers.base import Completion
from taleport.api.context import AppContext, build_context
from taleport.archive.service import fts_query
from taleport.core.errors import AppError
from taleport.db.database import Database
from taleport.notifications import rules
from tests.conftest import TEST_TOKEN, topic_payload
from tests.test_ai import FakeProvider

TODAY = date(2026, 11, 2)


def _draft(
    conn, platform="linkedin", text="Testo del post", theme_key=None, theme_title=None,
    topic_id=None, label="Tema",
) -> int:  # fmt: skip
    cursor = conn.execute(
        "INSERT INTO drafts (batch_id, topic_id, theme_key, theme_title, origin, source_label, "
        "platform, language, text) VALUES ('b', ?, ?, ?, 'theme', ?, ?, 'it', ?)",
        (topic_id, theme_key, theme_title, label, platform, text),
    )
    return int(cursor.lastrowid)


def _utc(day: date, hour: int) -> str:
    local = datetime.combine(day, time(hour), datetime.now().astimezone().tzinfo)
    return local.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _published(ctx: AppContext, results: dict, hour: int = 9, **draft) -> int:
    with ctx.db.connect() as conn:
        draft_id = _draft(conn, **draft)
    ctx.generator.publish(draft_id, published_at=_utc(TODAY - timedelta(days=3), hour))
    ctx.results.save(draft_id, results)
    return draft_id


# -- archive -------------------------------------------------------------------------


def test_fts_query_is_built_from_words_only() -> None:
    assert fts_query('intel  "artif" OR drop*') == '"intel"* "artif"* "or"* "drop"*'
    assert fts_query("  ") is None and fts_query(None) is None


def test_archive_search_follows_edits_and_filters(ctx: AppContext) -> None:
    with ctx.db.connect() as conn:
        a = _draft(conn, text="L'intelligenza artificiale cambia il marketing")
        b = _draft(conn, platform="instagram", text="Reels e caroselli per l'estate")
    ids = lambda **kw: [r["id"] for r in ctx.archive.posts(**kw)["rows"]]  # noqa: E731
    assert ids(q="intelligenza artif") == [a]
    assert ids(q="intelligènza") == [a]  # accents removed by the tokenizer
    assert ids(platform="instagram") == [b]
    ctx.generator.update_text(b, "Caroselli sull'intelligenza artificiale")
    assert set(ids(q="intelligenza")) == {a, b}
    ctx.generator.publish(a)
    assert ids(status="published") == [a]
    ctx.generator.delete(a)
    assert ids(q="intelligenza") == [b]
    assert ctx.archive.posts(q="caroselli")["total"] == 1
    with pytest.raises(AppError):
        ctx.archive.posts(status="lost")


def test_archive_themes_search(ctx: AppContext) -> None:
    topic = ctx.topics.create(topic_payload()).id
    with ctx.db.connect() as conn:
        conn.execute(
            "INSERT INTO themes (topic_id, day, key, title, summary, score, trend, item_count, "
            "source_count) VALUES (?, '2026-11-01', 'reels', 'Reels lunghi', 'Instagram allunga "
            "i video', 70, 'up', 4, 2), (?, '2026-10-20', 'seo', 'SEO locale', NULL, 40, 'flat', "
            "2, 1)",
            (topic, topic),
        )
    result = ctx.archive.themes(q="video")
    assert [r["title"] for r in result["rows"]] == ["Reels lunghi"]
    assert ctx.archive.themes(start=date(2026, 10, 25))["total"] == 1
    assert ctx.archive.themes(topic_id=topic)["total"] == 2


# -- results and priorities ----------------------------------------------------------


def test_results_only_on_published_posts(ctx: AppContext) -> None:
    with ctx.db.connect() as conn:
        draft_id = _draft(conn)
    with pytest.raises(AppError) as info:
        ctx.results.save(draft_id, {"likes": 3})
    assert info.value.code == "results.not_published"
    ctx.generator.publish(draft_id)
    ctx.results.save(draft_id, {"likes": 3, "comments": 1})
    assert ctx.generator.get(draft_id)["results"] == {
        "likes": 3, "comments": 1, "shares": None, "views": None,
    }  # fmt: skip
    ctx.results.save(draft_id, {})
    assert ctx.generator.get(draft_id)["results"] is None
    with pytest.raises(AppError):
        ctx.results.save(draft_id, {"likes": -1})


def test_summary_explains_the_platform_to_favour(ctx: AppContext) -> None:
    assert ctx.results.summary()["reasons"] == []
    _published(ctx, {"likes": 40, "comments": 12, "shares": 2})
    _published(ctx, {"likes": 30, "comments": 14, "shares": 4})
    _published(ctx, {"likes": 20, "comments": 1, "shares": 1}, platform="instagram")
    assert ctx.results.summary()["reasons"] == []  # instagram has a single post
    _published(ctx, {"likes": 25, "comments": 2, "shares": 0}, platform="instagram")
    summary = ctx.results.summary()
    assert summary["platforms"][0]["platform"] == "linkedin"
    assert summary["platforms"][0]["interactions"] == 51.0
    assert summary["reasons"] == [
        {"code": "platform", "params": {"platform": "linkedin", "metric": "comments",
                                        "value": 13.0}},
    ]  # fmt: skip


def test_today_shows_why_a_theme_has_priority(ctx: AppContext) -> None:
    topic = ctx.topics.create(topic_payload()).id
    _published(ctx, {"likes": 50, "comments": 20}, theme_key="reels", theme_title="Reels lunghi",
               topic_id=topic)  # fmt: skip
    _published(ctx, {"likes": 5}, theme_key="seo", theme_title="SEO locale", topic_id=topic)
    with ctx.db.connect() as conn:
        conn.execute(
            "INSERT INTO themes (topic_id, day, key, title, score, trend, item_count, "
            "source_count, position) VALUES (?, ?, 'reels', 'Reels più lunghi su Instagram', 80, "
            "'up', 5, 2, 0), (?, ?, 'tiktok', 'TikTok Shop', 60, 'new', 3, 1, 1)",
            (topic, TODAY.isoformat(), topic, TODAY.isoformat()),
        )
    themes = ctx.analysis.today_overview(TODAY)["topics"][0]["themes"]
    assert themes[0]["priority"] == {
        "code": "theme",
        "params": {"theme": "Reels lunghi", "metric": "comments", "value": 20, "posts": 1},
    }
    assert themes[1]["priority"] is None


# -- calendar ------------------------------------------------------------------------


def test_calendar_move_and_posting_times(ctx: AppContext) -> None:
    with ctx.db.connect() as conn:
        draft_id = _draft(conn, platform="instagram")
    week = (TODAY, TODAY + timedelta(days=6))
    assert [e["id"] for e in ctx.planner.calendar(*week)["unscheduled"]] == [draft_id]

    moved = ctx.planner.move(draft_id, TODAY + timedelta(days=2))
    assert moved["scheduled_at"] == "2026-11-04T18:00"  # instagram's default time
    ctx.planner.move(draft_id, TODAY + timedelta(days=3))
    assert ctx.generator.get(draft_id)["scheduled_at"] == "2026-11-05T18:00"  # time kept
    data = ctx.planner.calendar(*week)
    assert [(e["day"], e["time"]) for e in data["entries"]] == [("2026-11-05", "18:00")]
    assert data["unscheduled"] == []

    ctx.settings.update({"posting_times": {"instagram": "12:30"}})
    ctx.planner.move(draft_id, TODAY, "12:30")
    times = {t["platform"]: t for t in ctx.planner.posting_times()}
    assert times["instagram"]["time"] == "12:30" and times["linkedin"]["time"] == "08:30"
    with pytest.raises(AppError):
        ctx.settings.update({"posting_times": {"myspace": "10:00"}})

    ctx.generator.publish(draft_id, published_at=_utc(TODAY + timedelta(days=1), 21))
    entry = ctx.planner.calendar(*week)["entries"][0]
    assert (entry["day"], entry["time"], entry["status"]) == ("2026-11-03", "21:00", "published")
    with pytest.raises(AppError) as info:
        ctx.planner.move(draft_id, TODAY)
    assert info.value.code == "calendar.published"
    with pytest.raises(AppError):
        ctx.planner.calendar(TODAY, TODAY + timedelta(days=90))


def test_posting_time_learned_from_results(ctx: AppContext) -> None:
    for hour, likes in ((9, 5), (9, 7), (18, 40), (18, 30)):
        _published(ctx, {"likes": likes}, hour=hour)
    times = {t["platform"]: t for t in ctx.planner.posting_times()}
    assert times["linkedin"]["learned"] == {"time": "18:00", "posts": 2, "average": 35.0}
    assert times["instagram"]["learned"] is None


# -- notifications -------------------------------------------------------------------


class Toasts(list):
    def __call__(self, title: str, message: str) -> None:
        self.append((title, message))


def _summary(trigger="scheduled", status="completed", cells=(), topics=()) -> dict:
    return {"trigger": trigger, "status": status, "items_new": 7, "items_found": 20,
            "cells": list(cells), "topics": list(topics)}  # fmt: skip


def test_scan_notifications_and_dedupe(ctx: AppContext) -> None:
    toasts = Toasts()
    ctx.notifications.toaster = toasts
    failing = {"source": "reddit", "state": "error", "code": "collector.blocked"}
    ctx.notifications.after_scan(_summary(cells=[failing]), TODAY)
    ctx.notifications.after_scan(_summary("catchup", "partial", [failing]), TODAY)
    ctx.notifications.after_scan(_summary("manual"), TODAY)
    rows = ctx.notifications.list()["rows"]
    assert [r["kind"] for r in rows] == [
        "scan_completed",
        "scan_recovered",
        "source_failing",
        "scan_completed",
    ]  # fmt: skip  (newest first; reddit only once a day)
    assert rows[2]["params"] == {"source": "reddit", "code": "collector.blocked"}
    assert len(toasts) == 3  # the manual scan is watched in the window: no toast
    assert toasts[1] == ("Fonte non funzionante", toasts[1][1]) and "Reddit" in toasts[1][1]

    ctx.settings.update({"notify_windows": False, "language": "en"})
    ctx.notifications.after_scan(_summary(), TODAY)
    assert len(toasts) == 3
    assert ctx.notifications.list()["unread"] == 5
    ctx.notifications.mark_read([rows[0]["id"]])
    assert ctx.notifications.list()["unread"] == 4
    ctx.notifications.mark_read()
    ctx.notifications.clear()
    assert ctx.notifications.list() == {"unread": 0, "rows": []}


def test_spike_detection(ctx: AppContext, monkeypatch) -> None:
    topic = ctx.topics.create(topic_payload()).id
    counts = {TODAY: 24, **{TODAY - timedelta(days=d): 8 for d in (1, 2, 4)}}
    monkeypatch.setattr(rules, "_items_on", lambda _c, _t, day: counts.get(day, 0))
    with ctx.db.connect() as conn:
        spikes = rules.detect_spikes(conn, TODAY, [topic])
        assert spikes[0] == {"topic_id": topic, "topic": "AI marketing", "today": 24,
                                  "average": 8.0, "theme_id": None, "theme": ""}  # fmt: skip
        counts[TODAY] = 15  # less than twice the average
        assert rules.detect_spikes(conn, TODAY, [topic]) == []
        counts.update({TODAY: 30, TODAY - timedelta(days=1): 0, TODAY - timedelta(days=2): 0})
        assert rules.detect_spikes(conn, TODAY, [topic]) == []  # one day of history only

    counts.update({TODAY: 30, TODAY - timedelta(days=1): 8, TODAY - timedelta(days=2): 8})
    ctx.notifications.after_scan(_summary(topics=[{"id": topic}]), TODAY)
    ctx.notifications.after_scan(_summary(topics=[{"id": topic}]), TODAY)
    kinds = [r["kind"] for r in ctx.notifications.list()["rows"]]
    assert kinds.count("spike") == 1


# -- spending cap --------------------------------------------------------------------


@pytest.fixture
def paid(db: Database) -> tuple[AppContext, FakeProvider]:
    fake = FakeProvider([])
    ctx = build_context(
        db, TEST_TOKEN, collectors_factory=lambda: [], ai_provider_factory=lambda *a: fake
    )
    return ctx, fake


def _cost(usd: float) -> Completion:
    return Completion(text="", model="x", input_tokens=0, output_tokens=0, cost_usd=usd)


def test_spending_cap_blocks_paid_calls_and_warns(paid) -> None:
    ctx, fake = paid
    assert ctx.ai.resolve("openai")[0] == "openai"  # no cap
    ctx.settings.update({"spend_cap_usd": 1.0, "spend_warn_percent": 80})
    ctx.usage.record("openai", "test", _cost(0.5), paid=True)  # no notification hook here
    ctx.ai.recorder(fake, "test")(_cost(0.35))
    assert [r["kind"] for r in ctx.notifications.list()["rows"]] == ["spend_near"]
    assert ctx.ai.resolve("openai")[0] == "openai"  # 0.85 < 1.0

    ctx.ai.recorder(fake, "test")(_cost(0.2))
    assert ctx.ai.resolve("openai") == ("chat", None, "ai.spend_cap_reached")
    assert [r["kind"] for r in ctx.notifications.list()["rows"]] == ["spend_reached", "spend_near"]
    with pytest.raises(AppError) as info:
        ctx.ai.test_provider("openai")
    assert info.value.code == "ai.spend_cap_reached"

    fake.paid = False  # local models stay available
    assert ctx.ai.resolve("ollama")[0] == "ollama"


# -- API -----------------------------------------------------------------------------


def test_phase7_api(client: TestClient, ctx: AppContext) -> None:
    with ctx.db.connect() as conn:
        draft_id = _draft(conn, text="Post sulle newsletter")
    assert client.get("/api/archive/posts?q=newsletter").json()["total"] == 1
    assert client.get("/api/archive/themes").json() == {"total": 0, "rows": []}
    moved = client.put(f"/api/calendar/{draft_id}", json={"day": "2026-11-10"}).json()
    assert moved["scheduled_at"] == "2026-11-10T08:30"
    cal = client.get("/api/calendar?start=2026-11-09&end=2026-11-15").json()
    assert cal["entries"][0]["id"] == draft_id and len(cal["posting_times"]) == 5
    assert (
        client.put(f"/api/drafts/{draft_id}/results", json={"likes": 1}).json()["error"]["code"]
        == "results.not_published"
    )
    client.post(f"/api/drafts/{draft_id}/publish", json={})
    saved = client.put(f"/api/drafts/{draft_id}/results", json={"likes": 4, "views": 90}).json()
    assert saved["results"]["views"] == 90
    assert client.get("/api/results/summary").json()["posts"] == 1
    assert client.get("/api/notifications").json() == {"unread": 0, "rows": []}
    assert client.post("/api/notifications/read", json={}).status_code == 204
    usage = client.get("/api/ai/usage").json()
    assert usage["cap_usd"] is None and usage["cap_reached"] is False
