import pytest

from taleport.core.errors import AppError
from taleport.db.database import Database
from taleport.topics.models import MAX_TOPICS
from taleport.topics.service import TopicStore
from tests.conftest import topic_payload


def test_create_normalizes_lists_and_reads_back(db: Database) -> None:
    store = TopicStore(db)
    topic = store.create(
        topic_payload(
            keywords={"it": [" IA ", "ia", "", "marketing  digitale"]},
            editions=["it-IT", "it-IT"],
            hashtags=["#AI", "ai", "#Social Media"],
            sources=[
                {"kind": "subreddit", "value": "https://www.reddit.com/r/socialmedia/"},
                {"kind": "youtube_channel", "value": "https://www.youtube.com/@GoogleDevelopers"},
                {"kind": "rss", "value": "https://example.com/feed.xml"},
            ],
            style_examples=["  Primo post ", "", "Secondo"],
            platforms=["linkedin", "linkedin", "tiktok"],
        )
    )
    assert topic.keywords == {"it": ["IA", "marketing digitale"]}
    assert topic.editions == ["it-IT"]
    assert topic.hashtags == ["AI", "SocialMedia"]
    assert [(s.kind, s.value) for s in topic.sources] == [
        ("subreddit", "socialmedia"),
        ("youtube_channel", "@GoogleDevelopers"),
        ("rss", "https://example.com/feed.xml"),
    ]
    assert topic.style_examples == ["Primo post", "Secondo"]
    assert topic.platforms == ["linkedin", "tiktok"]
    assert store.get(topic.id) == topic


def test_keywords_required_for_selected_languages(db: Database) -> None:
    with pytest.raises(AppError) as info:
        TopicStore(db).create(topic_payload(editions=["es-ES"], keywords={"it": ["ia"]}))
    assert info.value.code == "topics.keywords_required"


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"name": ""}, "topics.invalid"),
        ({"editions": ["fr-FR"]}, "topics.invalid"),
        ({"style_examples": ["a"] * 6}, "topics.invalid"),
        ({"sources": [{"kind": "rss", "value": "not a url"}]}, "topics.invalid_source"),
        ({"sources": [{"kind": "subreddit", "value": "r/a b"}]}, "topics.invalid_source"),
    ],
)
def test_invalid_topics_are_rejected(db: Database, changes: dict, code: str) -> None:
    with pytest.raises(AppError) as info:
        TopicStore(db).create(topic_payload(**changes))
    assert info.value.code == code


def test_limit_of_ten_topics(db: Database) -> None:
    store = TopicStore(db)
    for i in range(MAX_TOPICS):
        store.create(topic_payload(name=f"Topic {i}"))
    with pytest.raises(AppError) as info:
        store.create(topic_payload(name="One too many"))
    assert info.value.code == "topics.limit"
    assert [t.position for t in store.list()] == list(range(MAX_TOPICS))


def test_update_toggle_delete(db: Database) -> None:
    store = TopicStore(db)
    topic = store.create(topic_payload(sources=[{"kind": "youtube_channel", "value": "@chan"}]))
    store.set_source_resolved(topic.id, "youtube_channel", "@chan", "UUplaylist")

    updated = store.update(
        topic.id, topic_payload(name="Renamed", sources=topic.model_dump()["sources"])
    )
    assert updated.name == "Renamed"
    # cached lookup survives an edit that keeps the source
    assert store.source_resolved(topic.id, "youtube_channel", "@chan") == "UUplaylist"

    assert store.set_active(topic.id, False).active is False
    assert store.active() == []

    store.delete(topic.id)
    with pytest.raises(AppError) as info:
        store.get(topic.id)
    assert info.value.status == 404
