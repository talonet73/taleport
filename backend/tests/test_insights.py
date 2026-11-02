"""Closed analysis functions, 'Ask' plans (validation, presets, AI and pasted answers), APIs."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient

from taleport.api.context import AppContext, build_context
from taleport.ask import functions as fn
from taleport.ask.plan import PRESETS, AskPlan
from taleport.ask.scope import Filters, Period, Scope
from taleport.core.errors import AppError
from taleport.db.database import Database
from tests.conftest import TEST_TOKEN, topic_payload
from tests.test_ai import FakeProvider

TODAY = date(2026, 11, 2)


def _stat(conn, topic_id, day, term, count, language="it", source="news", kind="keyword"):
    conn.execute(
        "INSERT INTO keyword_stats VALUES (?, ?, ?, ?, ?, ?, ?)",
        (topic_id, day.isoformat(), kind, term, language, source, count),
    )


def _item(conn, topic_id, day, n, source="news", language="it"):
    # Local noon of `day`, stored in UTC like the app does.
    tz = datetime.now().astimezone().tzinfo
    linked = datetime.combine(day, time(12), tz).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    cursor = conn.execute(
        "INSERT INTO items (source, url, canonical_url, title, title_key, language) "
        "VALUES (?, ?, ?, 't', 't', ?)",
        (
            source,
            f"https://x/{topic_id}/{day}/{n}/{source}",
            f"https://x/{topic_id}/{day}/{n}/{source}",
            language,
        ),
    )
    conn.execute(
        "INSERT INTO item_topics (item_id, topic_id, linked_at) VALUES (?, ?, ?)",
        (cursor.lastrowid, topic_id, linked),
    )


@pytest.fixture
def seeded(db: Database) -> tuple[Database, int, int]:
    """Two topics, 14 days: 'reels' rises, 'threads' fades, 'chatgpt' is new this week."""
    ctx = build_context(db, TEST_TOKEN, collectors_factory=lambda: [])
    t1 = ctx.topics.create(topic_payload(name="Uno")).id
    t2 = ctx.topics.create(topic_payload(name="Due")).id
    with db.connect() as conn:
        for back in range(14):
            day = TODAY - timedelta(days=back)
            this_week = back < 7
            _stat(conn, t1, day, "reels", 6 if this_week else 2)
            _stat(conn, t1, day, "threads", 1 if this_week else 4)
            if this_week:
                _stat(conn, t1, day, "chatgpt", 2)
                _stat(conn, t2, day, "tiktok shop", 3, language="en", source="reddit")
                _stat(conn, t1, day, "ai", 1, kind="hashtag")
            for n in range(5):
                _item(conn, t1, day, n)
            _item(conn, t2, day, 0, source="reddit", language="en")
        conn.execute(
            "INSERT INTO themes (topic_id, day, key, title, score, trend, item_count, "
            "source_count) VALUES (?, ?, 'reels', 'Reels', 80, 'up', 6, 2), "
            "(?, ?, 'threads', 'Threads', 30, 'down', 1, 1)",
            (t1, TODAY.isoformat(), t1, (TODAY - timedelta(days=10)).isoformat()),
        )
    return db, t1, t2


def week_scope(**kw) -> Scope:
    return Scope.build(Period(preset="last_7_days"), Filters(**kw), TODAY)


# -- periods -----------------------------------------------------------------------------


def test_periods_resolve() -> None:
    monday = date(2026, 11, 2)  # a Monday
    assert Period(preset="today").resolve(monday) == (monday, monday)
    assert Period(preset="last_7_days").resolve(monday) == (date(2026, 10, 27), monday)
    assert Period(preset="last_week").resolve(monday) == (date(2026, 10, 26), date(2026, 11, 1))
    assert Period(preset="this_month").resolve(monday) == (date(2026, 11, 1), monday)
    custom = Period(preset="custom", start=date(2026, 10, 1), end=date(2026, 12, 31))
    assert custom.resolve(monday) == (date(2026, 10, 1), monday)  # never in the future
    with pytest.raises(ValueError):
        Period(preset="custom", start=date(2026, 10, 2), end=date(2026, 10, 1))
    assert Scope.build(Period(), None, monday).previous().end == date(2026, 10, 26)


# -- functions ---------------------------------------------------------------------------


def test_collapse_subterms() -> None:
    # Found in the app: "intelligenza" and "artificiale" listed under "intelligenza artificiale".
    rows = [("intelligenza artificiale", 42), ("intelligenza", 23), ("artificiale", 17),
            ("instagram", 7), ("social media", 3), ("social", 10)]  # fmt: skip
    assert fn.collapse_subterms(rows) == [
        ("intelligenza artificiale", 42),
        ("instagram", 7),
        ("social media", 3),
        ("social", 10),
    ]  # "social" stays: it mostly appears on its own (3 < 0.7 * 10)


def test_top_keywords_with_shares_and_filters(seeded) -> None:
    db, t1, t2 = seeded
    with db.connect() as conn:
        result = fn.top_keywords(conn, week_scope(), limit=3)
        assert [r["term"] for r in result["rows"]] == ["reels", "tiktok shop", "chatgpt"]
        assert result["total_items"] == 42  # 6 per day over 7 days
        assert result["rows"][0]["share"] == round(100 * 42 / 42, 1)

        only_en = fn.top_keywords(conn, week_scope(languages=["en"]))
        assert [r["term"] for r in only_en["rows"]] == ["tiktok shop"]
        assert only_en["total_items"] == 7

        assert [r["term"] for r in fn.top_keywords(conn, week_scope(), "hashtag")["rows"]] == ["ai"]
        assert fn.top_keywords(conn, week_scope(topics=[t2]))["rows"][0]["term"] == "tiktok shop"


def test_emerging_and_declining(seeded) -> None:
    db, *_ = seeded
    with db.connect() as conn:
        result = fn.emerging_keywords(conn, week_scope())
    emerging = {r["term"]: r for r in result["emerging"]}
    assert set(emerging) == {"reels", "chatgpt", "tiktok shop"}
    assert emerging["reels"]["change_pct"] == 200 and emerging["chatgpt"]["change_pct"] is None
    assert [r["term"] for r in result["declining"]] == ["threads"]
    assert result["has_history"] and result["previous"]["end"] == "2026-10-26"


def test_no_history_means_no_emerging(seeded) -> None:
    db, *_ = seeded
    far_past = Scope.build(
        Period(preset="custom", start=TODAY - timedelta(days=13), end=TODAY - timedelta(days=7)),
        None,
        TODAY,
    )
    with db.connect() as conn:
        result = fn.emerging_keywords(conn, far_past)
    assert not result["has_history"] and result["emerging"] == [] and result["declining"] == []


def test_trend_compare_and_themes(seeded) -> None:
    db, t1, _ = seeded
    with db.connect() as conn:
        trend = fn.topic_trend(conn, week_scope(), limit=2)
        assert len(trend["days"]) == 7 and [s["term"] for s in trend["series"]] == [
            "reels",
            "tiktok shop",
        ]
        assert trend["series"][0]["values"] == [6] * 7
        assert fn.topic_trend(conn, week_scope(), ["Threads"])["series"][0]["values"] == [1] * 7

        last = Scope.build(
            Period(
                preset="custom", start=TODAY - timedelta(days=13), end=TODAY - timedelta(days=7)
            ),
            None,
            TODAY,
        )
        compared = fn.compare_periods(conn, last, week_scope(), limit=2)
        assert compared["rows"][0] == {"term": "reels", "a": 14, "b": 42}

        languages = fn.compare_languages(conn, week_scope())
        assert [g["key"] for g in languages["groups"]] == ["it", "en"]
        assert languages["groups"][1]["top"][0]["term"] == "tiktok shop"
        sources = fn.compare_sources(conn, week_scope())
        assert {g["key"]: g["items"] for g in sources["groups"]} == {"news": 35, "reddit": 7}

        themes = fn.top_themes(conn, week_scope())["rows"]
        assert [t["title"] for t in themes] == ["Reels"]  # "Threads" is outside the week

        daily = fn.daily_items(conn, week_scope())
        assert daily["totals"] == [6] * 7
        assert {s["source"] for s in daily["by_source"]} == {"news", "reddit"}


# -- plans -------------------------------------------------------------------------------


def test_plan_validation_rejects_anything_outside_the_closed_set() -> None:
    AskPlan.model_validate({"steps": [{"function": "top_keywords", "limit": 5}]})
    bad_plans = [
        {"steps": [{"function": "run_sql", "query": "DROP TABLE items"}]},
        {"steps": [{"function": "top_keywords", "limit": 500}]},
        {"steps": [{"function": "top_keywords", "sql": "SELECT 1"}]},
        {"steps": [{"function": "top_themes"}] * 5},
        {"steps": []},
        {"steps": [{"function": "top_keywords", "period": {"preset": "custom"}}]},
    ]
    for plan in bad_plans:
        with pytest.raises(ValueError):
            AskPlan.model_validate(plan)


def test_presets_run_without_ai(seeded) -> None:
    db, *_ = seeded
    ctx = build_context(db, TEST_TOKEN, collectors_factory=lambda: [])
    for preset in PRESETS:
        result = ctx.insights.run_preset(preset, TODAY)
        assert result["steps"] and result["preset"] == preset
    trending = ctx.insights.run_preset("trending_week", TODAY)
    assert [s["function"] for s in trending["steps"]] == ["top_keywords", "topic_trend"]
    with pytest.raises(AppError):
        ctx.insights.run_preset("nope")


@pytest.fixture
def fake() -> FakeProvider:
    return FakeProvider([])


def test_ask_with_provider_chat_and_unknown_topic(seeded, fake) -> None:
    db, t1, _ = seeded
    ctx = build_context(
        db, TEST_TOKEN, collectors_factory=lambda: [], ai_provider_factory=lambda *a: fake
    )
    plan = {"title": "Parole della settimana", "steps": [
        {"function": "top_keywords", "period": {"preset": "last_7_days"},
         "filters": {"topics": [t1]}},
    ]}  # fmt: skip
    fake.answers.append(json.dumps(plan))
    out = ctx.insights.ask("Quali parole sono in tendenza?", "openai")
    assert (
        out["title"] == "Parole della settimana" and out["steps"][0]["function"] == "top_keywords"
    )
    assert "Uno" in fake.calls[0][1] and "top_keywords" in fake.calls[0][0]

    handoff = ctx.insights.ask("Quali parole sono in tendenza?", "chat")["handoff"]
    assert "Quali parole sono in tendenza?" in handoff["prompt"]
    pasted = ctx.insights.parse_ask("q", f"```json\n{json.dumps(plan)}\n```")
    assert pasted["steps"][0]["result"]["rows"]

    with pytest.raises(AppError) as info:
        ctx.insights.parse_ask(
            "q", json.dumps({"steps": [{"function": "top_themes", "filters": {"topics": [999]}}]})
        )
    assert info.value.code == "ask.unknown_topic"
    with pytest.raises(AppError) as info:
        ctx.insights.parse_ask("q", '{"steps": [{"function": "delete_everything"}]}')
    assert info.value.code == "ai.invalid_pasted"


def test_insights_api(client: TestClient, ctx: AppContext) -> None:
    week = client.get("/api/week").json()
    assert len(week["daily"]["days"]) == 7 and week["stats"]["items"] == 0
    trends = client.get("/api/trends?period=last_30_days&language=it").json()
    assert set(trends) >= {
        "keywords",
        "hashtags",
        "changes",
        "trend",
        "cloud",
        "by_language",
        "by_source",
    }
    assert trends["scope"]["languages"] == ["it"]
    assert client.get("/api/trends?period=custom").json()["error"]["code"] == "validation"
    assert "trending_week" in client.get("/api/ask/presets").json()
    assert client.post("/api/ask/preset/emerging").status_code == 200
    assert (
        client.post("/api/ask", json={"question": "  "}).json()["error"]["code"]
        == "ask.question_required"
    )
