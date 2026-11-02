"""Post generator: fact-check, rendering, text extraction, drafts lifecycle, 'already covered'."""

from __future__ import annotations

import base64
import io
import json

import pytest
from fastapi.testclient import TestClient

from taleport.api.context import AppContext, build_context
from taleport.core.errors import AppError
from taleport.db.database import Database
from taleport.generator.extract import MAX_CONTENT_CHARS, extract_text, limit_content
from taleport.generator.factcheck import check_facts
from taleport.generator.render import render_copy_text
from taleport.generator.schemas import GeneratedPost
from tests.conftest import TEST_TOKEN
from tests.test_ai import FakeProvider, _analysed_topic

# -- fact-check ------------------------------------------------------------------------

CORPUS = (
    "Meta Advantage Plus campaigns cut costs by 32% for small advertisers in 2026. "
    "Mark Zuckerberg said: «AI will write most ads». TikTok Shop expands in Europe."
)


def test_factcheck_flags_only_what_is_not_in_the_sources() -> None:
    text = (
        "Le campagne Advantage Plus hanno ridotto i costi del 32% nel 2026. "
        "Secondo uno studio di Harvard Business School sono cresciute del 45%. "
        "OpenAI prepara qualcosa di simile, dice Sam Altman. "
        "Ecco 3 consigli per Instagram. Mark Zuckerberg ha detto «AI will write most ads». "
        "E ha aggiunto «the future is fully automated advertising»."
    )
    warnings = check_facts(text, CORPUS, allowed=["Instagram"])
    values = {(w["kind"], w["value"]) for w in warnings}
    assert ("number", "45%") in values
    assert ("name", "Harvard Business School") in values
    assert ("name", "OpenAI") in values
    assert ("name", "Sam Altman") in values
    assert ("quote", "the future is fully automated advertising") in values
    flagged = {v for _, v in values}
    assert not flagged & {
        "32%",
        "2026",
        "3",
        "Mark Zuckerberg",
        "AI will write most ads",
        "Instagram",
    }


def test_factcheck_ignores_sentence_initial_capitals_and_hashtags() -> None:
    text = (
        "Oggi parliamo di TikTok Shop. Scopri di più! #Marketing2026 #AI\n\n"
        "#PMI #SocialMediaMarketing"
    )
    assert check_facts(text, CORPUS) == []


def test_factcheck_names_with_numbers_and_video_timecodes() -> None:
    # Found in the app: "Il Sole 24 Ore" was split, and script times read as numbers.
    text = "Secondo Il Sole 24 Ore va così.\n[0-3s] Ciao\n[20-40s] Poi mostra il negozio (3-20s)"
    assert check_facts(text, CORPUS) == [{"kind": "name", "value": "Il Sole 24 Ore"}]


# -- rendering -------------------------------------------------------------------------


def test_render_copy_text_per_platform() -> None:
    linkedin = GeneratedPost(
        platform="linkedin", language="it", hook="Una domanda:", text="Corpo del post.",
        hashtags=["#marketing", "AI"],
    )  # fmt: skip
    assert render_copy_text(linkedin, "it") == "Una domanda:\n\nCorpo del post.\n\n#marketing #AI"

    youtube = GeneratedPost(
        platform="youtube", language="en", title="Title", text="Description", outline=["One", "Two"]
    )
    assert render_copy_text(youtube, "en") == "Title\n\nDescription\n\nOutline:\n- One\n- Two"

    tiktok = GeneratedPost.model_validate({
        "platform": "TikTok", "language": "es", "hook": "¿Sabías…?", "text": "Pie #ia",
        "script": [{"time": "0-3s", "scene": "Primer plano", "voiceover": "Hola"}],
        "hashtags": ["ia", "marketing"], "sources_used": ["[2]", "3"],
    })  # fmt: skip
    rendered = render_copy_text(tiktok, "es")
    assert "[0-3s] Hola (Primer plano)" in rendered and rendered.endswith("#marketing")
    assert tiktok.sources_used == [2, 3]


# -- text extraction ---------------------------------------------------------------------


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def test_extract_txt_docx_and_errors() -> None:
    assert extract_text("note.txt", _b64(b"Ciao mondo")) == "Ciao mondo"

    import docx

    document = docx.Document()
    document.add_paragraph("Primo paragrafo")
    document.add_paragraph("Secondo paragrafo")
    buffer = io.BytesIO()
    document.save(buffer)
    assert extract_text("doc.docx", _b64(buffer.getvalue())) == "Primo paragrafo\nSecondo paragrafo"

    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    pdf = io.BytesIO()
    writer.write(pdf)
    with pytest.raises(AppError) as info:
        extract_text("scan.pdf", _b64(pdf.getvalue()))
    assert info.value.code == "content.empty"  # e.g. a scanned PDF without text

    for name, code in [("x.exe", "content.unsupported_format"), ("x.docx", "content.unreadable")]:
        with pytest.raises(AppError) as info:
            extract_text(name, _b64(b"not a document"))
        assert info.value.code == code


def test_limit_content() -> None:
    text, truncated = limit_content("a" * 100)
    assert not truncated
    long = ("parola " * 2000 + "\n\n") * 6
    text, truncated = limit_content(long)
    assert truncated and len(text) <= MAX_CONTENT_CHARS


# -- service -----------------------------------------------------------------------------


@pytest.fixture
def fake() -> FakeProvider:
    return FakeProvider([])


@pytest.fixture
def gen_ctx(db: Database, fake: FakeProvider) -> AppContext:
    return build_context(
        db, TEST_TOKEN, collectors_factory=lambda: [], ai_provider_factory=lambda *a: fake
    )


def _posts(*posts: dict) -> str:
    return json.dumps({"posts": list(posts)})


LINKEDIN = {
    "platform": "linkedin", "language": "it", "variant": 1, "hook": "Lo sapevi?",
    "text": "Le campagne Advantage Plus crescono del 99% secondo Gartner Research.",
    "hashtags": ["marketing"], "image_idea": "Grafico", "image_prompt": "a chart",
    "sources_used": [1],
}  # fmt: skip


def test_generate_from_theme_saves_drafts_with_sources_and_warnings(
    gen_ctx: AppContext, fake
) -> None:
    _analysed_topic(gen_ctx)
    theme = gen_ctx.analysis.today_overview()["topics"][0]["themes"][0]
    fake.answers.append(_posts(LINKEDIN, {**LINKEDIN, "platform": "facebook", "text": "Ciao"},
                               {**LINKEDIN, "language": "fr"}))  # fmt: skip

    out = gen_ctx.generator.generate_from_theme(
        theme["id"], ["linkedin", "facebook"], ["it"], mode="openai"
    )
    assert out["mode"] == "openai" and len(out["drafts"]) == 2  # the French one is dropped
    draft = out["drafts"][0]
    assert draft["platform"] == "linkedin" and draft["text"].startswith("Lo sapevi?")
    assert draft["sources"][0]["url"].startswith("https://ex.com/")
    kinds = {(w["kind"], w["value"]) for w in draft["fact_warnings"]}
    assert ("number", "99%") in kinds and ("name", "Gartner Research") in kinds
    assert "Fonti (usa solo queste)" in fake.calls[0][1] and "[1]" in fake.calls[0][1]

    stats = gen_ctx.analysis.today_overview()["stats"]
    assert stats["posts_generated"] == 2 and stats["posts_published_week"] == 0

    with pytest.raises(AppError) as info:
        gen_ctx.generator.generate_from_theme(
            theme["id"], ["linkedin", "instagram"], ["it", "en", "es"], 3
        )
    assert info.value.code == "generator.too_many"


def test_generate_via_chat_and_pasted_answer(gen_ctx: AppContext) -> None:
    _analysed_topic(gen_ctx)
    theme_id = gen_ctx.analysis.today_overview()["topics"][0]["themes"][0]["id"]
    out = gen_ctx.generator.generate_from_theme(theme_id, ["linkedin"], ["it"], mode="chat")
    assert out["handoff"]["copied"] and "linkedin" in out["handoff"]["prompt"]

    pasted = f"Ecco i post:\n```json\n{_posts(LINKEDIN)}\n```"
    saved = gen_ctx.generator.parse_from_theme(theme_id, ["linkedin"], ["it"], pasted)
    assert saved["mode"] == "chat" and saved["drafts"][0]["ai_mode"] == "chat"


def test_draft_lifecycle_and_already_covered(gen_ctx: AppContext, fake) -> None:
    topic_id = _analysed_topic(gen_ctx)
    theme = gen_ctx.analysis.today_overview()["topics"][0]["themes"][0]
    fake.answers.append(_posts(LINKEDIN))
    draft = gen_ctx.generator.generate_from_theme(theme["id"], ["linkedin"], ["it"], mode="openai")[
        "drafts"
    ][0]

    fake.answers.append(_posts({**LINKEDIN, "text": "Versione nuova senza numeri."}))
    regenerated = gen_ctx.generator.regenerate(draft["id"], "openai")["draft"]
    assert regenerated["id"] == draft["id"] and "Versione nuova" in regenerated["text"]
    assert regenerated["fact_warnings"] == []
    assert "Versione precedente" not in fake.calls[-1][1]  # the old text is passed as "covered"
    assert "Lo sapevi?" in fake.calls[-1][1]

    edited = gen_ctx.generator.update_text(draft["id"], "Testo mio con il 77% in più.")
    assert edited["edited"] and edited["fact_warnings"][0]["value"] == "77%"

    scheduled = gen_ctx.generator.schedule(draft["id"], "2026-11-05T09:00")
    assert scheduled["status"] == "scheduled" and scheduled["scheduled_at"] == "2026-11-05T09:00"

    published = gen_ctx.generator.publish(draft["id"], "https://linkedin.com/posts/1")
    assert published["status"] == "published" and published["publication"]["url"].startswith(
        "https://"
    )
    overview = gen_ctx.analysis.today_overview()
    assert overview["stats"]["posts_published_week"] == 1
    assert next(t for t in overview["topics"][0]["themes"] if t["id"] == theme["id"])["covered"]

    # A re-analysis keeps "covered" (matched by theme key, not by id)...
    gen_ctx.analysis.analyze(topic_id)
    assert gen_ctx.analysis.today_overview()["topics"][0]["themes"][0]["covered"]
    # ...and the next prompt lists it among the themes not to repeat.
    theme_id = gen_ctx.analysis.today_overview()["topics"][0]["themes"][0]["id"]
    fake.answers.append(_posts(LINKEDIN))
    gen_ctx.generator.generate_from_theme(theme_id, ["linkedin"], ["it"], mode="openai")
    assert f"- {theme['title']}" in fake.calls[-1][1]

    assert gen_ctx.generator.unpublish(draft["id"])["status"] == "scheduled"
    gen_ctx.generator.delete(draft["id"])
    with pytest.raises(AppError):
        gen_ctx.generator.get(draft["id"])


def test_long_content_series(gen_ctx: AppContext, fake) -> None:
    content = "Il report annuale mostra che il 40% delle PMI usa l'AI per i social. " * 10
    fake.answers.append(_posts(
        {**LINKEDIN, "series_index": 1, "text": "Il 40% delle PMI usa l'AI."},
        {**LINKEDIN, "series_index": 2, "text": "Il 12% no."},
    ))  # fmt: skip
    out = gen_ctx.generator.generate_long(
        content, "Report PMI", 2, ["linkedin"], "it", mode="openai"
    )
    assert [d["series_index"] for d in out["drafts"]] == [1, 2] and not out["truncated"]
    assert out["drafts"][0]["fact_warnings"] == []
    assert out["drafts"][1]["fact_warnings"][0]["value"] == "12%"
    assert (
        out["drafts"][0]["origin"] == "long_content"
        and out["drafts"][0]["source_label"] == "Report PMI"
    )

    with pytest.raises(AppError) as info:
        gen_ctx.generator.generate_long("troppo corto", "", 2, ["linkedin"], "it", mode="openai")
    assert info.value.code == "content.too_short"


def test_generator_api(client: TestClient) -> None:
    response = client.post(
        "/api/content/extract", json={"file_name": "a.txt", "file_base64": _b64(b"Testo di prova")}
    )
    assert response.json() == {"text": "Testo di prova", "truncated": False, "characters": 14}
    assert client.get("/api/drafts").json() == []
    assert (
        client.post(
            "/api/generator/theme", json={"theme_id": 1, "platforms": [], "languages": ["it"]}
        ).json()["error"]["code"]
        == "generator.platforms_required"
    )
    assert client.get("/api/drafts/999").status_code == 404
