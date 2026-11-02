from taleport.collectors.base import CollectedItem
from taleport.collectors.text import (
    canonical_url,
    excerpt,
    matches_any,
    near_duplicate,
    normalize_title,
    or_query,
    title_tokens,
)
from taleport.db.database import Database
from taleport.scan.items import ItemRepository, filter_for_topic
from taleport.topics.service import TopicStore
from tests.conftest import topic_payload


def test_canonical_url_drops_tracking_and_variants() -> None:
    a = canonical_url("http://www.Example.com/news/story/?utm_source=x&id=3&fbclid=abc#top")
    b = canonical_url("https://example.com/news/story?id=3")
    assert a == b == "https://example.com/news/story?id=3"
    assert canonical_url("https://youtu.be/abc123") == canonical_url(
        "https://m.youtube.com/watch?v=abc123&feature=share&t=10"
    )


def test_normalize_title_strips_publisher_accents_and_punctuation() -> None:
    assert normalize_title("L'IA è già qui! - Il Sole 24 ORE", "Il Sole 24 ORE") == "l ia e gia qui"


def test_near_duplicate_needs_long_similar_titles() -> None:
    a = title_tokens(normalize_title("OpenAI launches new model for marketing teams today"))
    b = title_tokens(normalize_title("OpenAI launches new model for marketing teams"))
    c = title_tokens(normalize_title("Google launches a phone"))
    assert near_duplicate(a, b)
    assert not near_duplicate(a, c)
    assert not near_duplicate(title_tokens("ai news"), title_tokens("ai news"))  # too short


def test_matching_and_queries() -> None:
    assert matches_any("New rules for Social  Media ads", ["social media"])
    assert not matches_any("socialmediamarketing", ["social media"])
    assert matches_any("Città più green", ["città"])
    assert or_query(["social media", "ads"]) == '("social media" OR ads)'
    assert or_query(["ads"]) == "ads"
    assert or_query(["a b", "c"], separator="|") == '"a b"|c'


def test_excerpt_is_short_and_html_free() -> None:
    text = excerpt("<p>" + "parola " * 200 + "</p>")
    assert len(text) <= 301 and text.endswith("…") and "<" not in text


def _item(url: str, title: str, **kw) -> CollectedItem:
    return CollectedItem(source=kw.pop("source", "news"), url=url, title=title, **kw)


def test_repository_deduplicates_by_url_and_title(db: Database) -> None:
    store = TopicStore(db)
    t1 = store.create(topic_payload(name="One"))
    t2 = store.create(topic_payload(name="Two"))
    repo = ItemRepository(db)

    first = repo.save(
        [
            _item(
                "https://a.com/x?utm_source=feed", "Meta changes the Instagram feed algorithm again"
            ),
            _item("https://a.com/x", "Meta changes the Instagram feed algorithm again"),  # same URL
            _item(
                "https://b.com/y", "Meta changes Instagram feed algorithm again"
            ),  # near-dup title
            _item("https://c.com/z", "Totally different story about LinkedIn"),
        ],
        t1.id,
        None,
    )
    assert (first.found, first.new) == (4, 2)

    # Another topic seeing the same story: no new item, but it gets linked.
    second = repo.save(
        [_item("https://a.com/x", "Meta changes the Instagram feed algorithm again")], t2.id, None
    )
    assert second.new == 0
    assert len(repo.for_topic(t2.id)) == 1

    # Short identical titles (e.g. trend terms) are not merged across URLs.
    third = repo.save(
        [
            _item("https://t.com/1", "nasa", source="trends"),
            _item("https://t.com/2", "nasa", source="trends"),
        ],
        t1.id,
        None,
    )
    assert third.new == 2

    # ...unless the excerpt is identical too (a post cross-posted to several subreddits).
    body = "Looking to start working remotely: any legitimate websites for beginners?"
    fourth = repo.save(
        [
            _item("https://reddit.com/r/a/comments/1", "Work", source="reddit", excerpt=body),
            _item("https://reddit.com/r/b/comments/2", "Work", source="reddit", excerpt=body),
        ],
        t1.id,
        None,
    )
    assert fourth.new == 1


def test_exclusions_filter_items(db: Database) -> None:
    topic = TopicStore(db).create(topic_payload(exclude=["crypto", "bitcoin price"]))
    items = [
        _item("https://a.com/1", "Crypto ads are back"),
        _item("https://a.com/2", "AI news", excerpt="talks about the bitcoin price"),
        _item("https://a.com/3", "AI and marketing"),
    ]
    assert [i.url for i in filter_for_topic(topic, items)] == ["https://a.com/3"]
