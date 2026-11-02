from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from taleport.analysis.keywords import KeywordExtractor
from taleport.analysis.questions import extract_questions
from taleport.analysis.scoring import ScoreInput, hot_score
from taleport.analysis.service import today_local
from taleport.analysis.text import detect_language, extract_hashtags, normalize_term
from taleport.analysis.themes import Doc, build_themes
from taleport.api.context import AppContext
from taleport.collectors.base import CollectedItem
from tests.conftest import FakeCollector, topic_payload

# -- text helpers ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("Come usare l'intelligenza artificiale per i post su Instagram e non solo", "it"),
        ("How to use artificial intelligence for your Instagram posts and more", "en"),
        ("Cómo usar la inteligencia artificial para los posts de Instagram y más", "es"),
        ("ChatGPT", None),
    ],
)
def test_detect_language(text: str, language: str | None) -> None:
    assert detect_language(text) == language


def test_normalize_term_handles_elisions_and_stopwords() -> None:
    assert normalize_term("sull’intelligenza artificiale") == "intelligenza artificiale"
    assert normalize_term("L'OMS") == "oms"
    assert normalize_term("the Instagram") == "instagram"
    assert normalize_term("nuovo") is None
    assert normalize_term("2026") is None


def test_hashtags() -> None:
    assert extract_hashtags("Ciao #AI e #MarketingDigitale, non questo#no né #1") == [
        "ai",
        "marketingdigitale",
    ]


def test_keyword_extractor_returns_normalized_pairs() -> None:
    terms = KeywordExtractor().extract(
        "Meta lancia nuovi strumenti di intelligenza artificiale "
        "per gli inserzionisti su Instagram",
        "it",
    )
    assert 0 < len(terms) <= 6
    keys = [key for key, _ in terms]
    assert all(key == key.lower() for key in keys)
    assert any("instagram" in key or "inserzionisti" in key for key in keys)


def test_questions_from_comments_and_posts() -> None:
    texts = [
        "Great video. How do I schedule Reels from desktop? Thanks!",
        "[Question] How do I schedule reels from desktop?",  # duplicate after cleanup
        "Is this real?",  # too short
        "¿Funciona también para cuentas de empresa en Instagram?",
    ]
    assert extract_questions(texts) == [
        "How do I schedule Reels from desktop?",
        "¿Funciona también para cuentas de empresa en Instagram?",
    ]


# -- scoring ---------------------------------------------------------------------------


def test_hot_score_new_and_trends() -> None:
    score, trend, details = hot_score(ScoreInput(today=5, previous_days=[], sources=2))
    assert trend == "new" and 0 <= score <= 100 and details["average"] is None

    _, up, _ = hot_score(ScoreInput(today=10, previous_days=[2, 2, 3], sources=2))
    _, down, _ = hot_score(ScoreInput(today=1, previous_days=[8, 6], sources=1))
    _, flat, _ = hot_score(ScoreInput(today=5, previous_days=[5, 5], sources=1))
    assert (up, down, flat) == ("up", "down", "flat")


def test_hot_score_grows_with_volume_and_sources() -> None:
    base = hot_score(ScoreInput(today=3, previous_days=[3, 3], sources=1))[0]
    more = hot_score(ScoreInput(today=20, previous_days=[3, 3], sources=1))[0]
    wider = hot_score(ScoreInput(today=3, previous_days=[3, 3], sources=4))[0]
    assert more > base and wider > base
    assert hot_score(ScoreInput(today=500, previous_days=[0], sources=9))[0] == 100


# -- theme grouping --------------------------------------------------------------------


def test_build_themes_skips_topic_keywords_and_singletons() -> None:
    docs = [
        Doc(1, frozenset({"intelligenza artificiale", "meta ads", "inserzionisti"}), "news"),
        Doc(2, frozenset({"intelligenza artificiale", "meta ads", "budget"}), "reddit"),
        Doc(3, frozenset({"intelligenza artificiale", "meta ads"}), "news", engagement=5),
        Doc(4, frozenset({"intelligenza artificiale", "tiktok shop"}), "youtube"),
        Doc(5, frozenset({"intelligenza artificiale", "tiktok shop", "budget"}), "news"),
        Doc(6, frozenset({"intelligenza artificiale", "chatbot"}), "news"),
    ]
    themes = build_themes(docs, exclude={"intelligenza artificiale", "intelligenza", "artificiale"})
    assert [t.key for t in themes] == ["meta ads", "tiktok shop"]
    assert [d.item_id for d in themes[0].members] == [1, 2, 3]
    assert themes[0].sources == {"news", "reddit"}
    assert all(6 not in [d.item_id for d in t.members] for t in themes)


# -- service ---------------------------------------------------------------------------


def _news(n: int, title: str, source: str = "news", **kw) -> CollectedItem:
    return CollectedItem(
        source=source, url=f"https://ex.com/{source}/{n}", title=title, language="en", **kw
    )


STORIES = [
    _news(1, "Meta Advantage Plus campaigns get new creative tools for advertisers"),
    _news(2, "Advertisers test Meta Advantage Plus campaigns with generative video"),
    _news(3, "Why Meta Advantage Plus campaigns cut costs for small advertisers", source="reddit",
          excerpt="How do I set up Advantage Plus campaigns for a local shop?"),
    _news(4, "TikTok Shop expands affiliate program in Europe"),
    _news(5, "Creators earn more from TikTok Shop affiliate program", source="youtube",
          extra={"comments": ["Does the TikTok Shop affiliate program work in Italy?"]}),
    _news(6, "LinkedIn tests a new newsletter analytics dashboard"),
]  # fmt: skip


def test_scan_triggers_analysis_and_today_overview(
    ctx: AppContext, collectors: list, client: TestClient
) -> None:
    collectors.append(FakeCollector("news", STORIES))
    topic = ctx.topics.create(
        topic_payload(editions=["en-US"], keywords={"en": ["social media marketing"]}, hashtags=[])
    )
    ctx.scans.start("manual")
    ctx.scans.wait(10)

    overview = client.get("/api/today").json()
    assert overview["stats"]["items_today"] == 6
    section = overview["topics"][0]
    assert section["topic"]["id"] == topic.id and section["items_today"] == 6
    titles = [t["title"].lower() for t in section["themes"]]
    assert any("advantage" in t for t in titles)
    assert any("tiktok shop" in t or "affiliate" in t for t in titles)
    first = section["themes"][0]
    assert first["trend"] == "new" and 0 < first["score"] <= 100
    assert first["representative"]["url"].startswith("https://ex.com/")

    detail = client.get(f"/api/themes/{first['id']}").json()
    assert len(detail["trend7"]) == 7 and detail["trend7"][-1]["day"] == today_local().isoformat()
    assert detail["trend7"][-1]["count"] >= 2
    assert detail["items"] and detail["score_details"]["components"]
    all_questions = [
        q
        for t in section["themes"]
        for q in client.get(f"/api/themes/{t['id']}").json()["questions"]
    ]
    assert any(q.endswith("?") for q in all_questions)

    with ctx.db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM keyword_stats").fetchone()[0] > 0
        assert conn.execute("SELECT COUNT(*) FROM items WHERE terms IS NULL").fetchone()[0] == 0
    assert client.get("/api/themes/999").status_code == 404


def test_history_changes_the_trend(ctx: AppContext) -> None:
    topic = ctx.topics.create(
        topic_payload(editions=["en-US"], keywords={"en": ["social media marketing"]}, hashtags=[])
    )
    ctx.items.save(STORIES, topic.id, None)
    ctx.analysis.analyze(topic.id)
    with ctx.db.connect() as conn:
        key = conn.execute("SELECT key FROM themes ORDER BY position LIMIT 1").fetchone()["key"]
        yesterday = (today_local() - timedelta(days=1)).isoformat()
        # Yesterday the same term appeared in 9 items: today's 2-3 means "down".
        conn.execute(
            "INSERT INTO keyword_stats VALUES (?, ?, 'keyword', ?, 'en', 'news', 9)",
            (topic.id, yesterday, key),
        )
    ctx.analysis.analyze(topic.id)
    with ctx.db.connect() as conn:
        row = conn.execute(
            "SELECT trend, score_details FROM themes WHERE key = ?", (key,)
        ).fetchone()
    assert row["trend"] == "down"
    assert '"yesterday": 9' in row["score_details"]
