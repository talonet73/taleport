"""Reference documents (Word, PDF, PowerPoint) and tone-of-voice profiles."""

from __future__ import annotations

import base64
import io
import json

import pytest
from fastapi.testclient import TestClient

from taleport.ai import prompts
from taleport.api.context import AppContext, build_context
from taleport.core.errors import AppError
from taleport.db.database import Database
from taleport.generator.extract import extract_text
from tests.conftest import TEST_TOKEN, topic_payload
from tests.test_ai import FakeProvider, _analysed_topic

SPEECH = (
    "Amici, oggi non vi parlo di numeri. Vi parlo di cuore. La Roma non si tifa, si vive. "
    "Abbiamo vinto il derby 2-1 con un gol di Dybala su punizione e uno di Pellegrini nel finale. "
    "E allora? E allora cantiamo, perché questa città lo merita. Daje Roma, sempre."
) * 2

VOICE = {
    "name": "Tifoso appassionato",
    "guide": [
        "Parla al pubblico come ad amici",
        "Frasi brevi, domande retoriche",
        "Evita il gergo tecnico",
    ],
    "examples": ["La Roma non si tifa, si vive.", "E allora? E allora cantiamo"],
}  # fmt: skip
POST = {"platform": "instagram", "language": "it", "text": "La Roma non si tifa, si vive. 2-1!",
        "hashtags": "#roma #derby"}  # fmt: skip


@pytest.fixture
def fake() -> FakeProvider:
    return FakeProvider([])


@pytest.fixture
def vctx(db: Database, fake: FakeProvider) -> AppContext:
    return build_context(
        db, TEST_TOKEN, collectors_factory=list, ai_provider_factory=lambda *a: fake,
        start_video_worker=False,
    )  # fmt: skip


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


# -- documents -------------------------------------------------------------------------------


def test_extract_pptx_slides_tables_and_notes() -> None:
    from pptx import Presentation
    from pptx.util import Inches

    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[1])
    slide.shapes.title.text = "Il derby"
    slide.placeholders[1].text = "Dybala su punizione"
    table = slide.shapes.add_table(2, 2, Inches(1), Inches(4), Inches(4), Inches(1)).table
    table.cell(0, 0).text, table.cell(0, 1).text = "Roma", "2"
    slide.notes_slide.notes_text_frame.text = "Ricordare i tifosi"
    deck.slides.add_slide(deck.slide_layouts[6])  # empty slide: skipped
    buffer = io.BytesIO()
    deck.save(buffer)
    text = extract_text("talk.pptx", _b64(buffer.getvalue()))
    assert text.startswith("[1]\nIl derby\nDybala su punizione")
    assert "Roma | 2" in text and "Ricordare i tifosi" in text and "[2]" not in text


def test_extract_docx_tables() -> None:
    import docx

    document = docx.Document()
    document.add_paragraph("Intro")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text, table.rows[0].cells[1].text = "Gol", "Dybala"
    buffer = io.BytesIO()
    document.save(buffer)
    assert extract_text("a.docx", _b64(buffer.getvalue())) == "Intro\nGol | Dybala"


# -- profiles --------------------------------------------------------------------------------


def test_profiles_crud_and_one_voice_per_topic(client: TestClient, ctx: AppContext) -> None:
    topic = ctx.topics.create(topic_payload())
    first = client.post("/api/voices", json={
        "name": "  Ironico  ", "guide": "- frasi brevi", "examples": ["«Daje»", "Daje", ""],
        "topic_ids": [topic.id, 999],
    }).json()  # fmt: skip
    assert first["name"] == "Ironico" and first["examples"] == ["Daje"]
    assert first["topic_ids"] == [topic.id]  # unknown topics dropped
    second = client.post("/api/voices", json={"name": "Serio", "topic_ids": [topic.id]}).json()
    profiles = {p["name"]: p for p in client.get("/api/voices").json()}
    assert profiles["Ironico"]["topic_ids"] == [] and profiles["Serio"]["topic_ids"] == [topic.id]
    assert ctx.voices.for_topic(topic.id)["id"] == second["id"]

    edited = client.put(f"/api/voices/{first['id']}", json={"name": "Ironico 2"}).json()
    assert edited["name"] == "Ironico 2"
    assert client.post("/api/voices", json={"name": "  "}).status_code == 400
    assert client.delete(f"/api/voices/{first['id']}").status_code == 204
    assert client.get("/api/voices").json()[0]["name"] == "Serio"
    assert client.put("/api/voices/12345", json={"name": "x"}).status_code == 404


def test_voice_analysis_with_provider_and_chat(vctx: AppContext, fake: FakeProvider) -> None:
    documents = [{"name": "discorso.docx", "text": SPEECH}]
    fake.answers.append(json.dumps(VOICE))
    out = vctx.voices.analyze(documents, "openai")
    voice = out["voice"]
    assert voice["name"] == "Tifoso appassionato" and voice["sources"] == ["discorso.docx"]
    assert voice["guide"].startswith("- Parla al pubblico") and len(voice["examples"]) == 2
    assert "=== discorso.docx ===" in fake.calls[0][1] and "Daje Roma" in fake.calls[0][1]

    handoff = vctx.voices.analyze(documents, "chat")
    assert handoff["mode"] == "chat" and "Daje Roma" in handoff["handoff"]["prompt"]
    parsed = vctx.voices.parse_analysis(["discorso.docx"], json.dumps({**VOICE, "name": ""}))
    assert parsed["voice"]["name"] == "discorso"  # falls back to the file name

    with pytest.raises(AppError) as info:
        vctx.voices.analyze([{"name": "a.txt", "text": "corto"}], "openai")
    assert info.value.code == "content.too_short"


# -- posts from reference documents ----------------------------------------------------------


def test_reference_posts_in_the_documents_voice_and_save_it(
    vctx: AppContext, fake: FakeProvider
) -> None:
    topic = vctx.topics.create(topic_payload())
    answer = {"topics": ["Derby vinto", "Passione dei tifosi"], "voice": VOICE,
              "posts": [POST, {**POST, "platform": "linkedin"}]}  # fmt: skip
    fake.answers.append(json.dumps(answer))
    out = vctx.generator.generate_from_reference(
        [{"name": "discorso.pdf", "text": SPEECH}], ["instagram"], ["it"], count=1,
        voice="reference", topic_id=topic.id, save_voice="", mode="openai",
    )  # fmt: skip
    assert len(out["drafts"]) == 1 and out["drafts"][0]["platform"] == "instagram"
    assert out["topics"] == ["Derby vinto", "Passione dei tifosi"]
    assert out["drafts"][0]["theme_title"] == "Derby vinto, Passione dei tifosi"
    prompt = fake.calls[0][1]
    assert "stesso tono di voce dei documenti" in prompt and "Daje Roma" in prompt
    profile = out["voice_profile"]
    assert profile["name"] == "Tifoso appassionato" and profile["topic_ids"] == [topic.id]
    assert profile["sources"] == ["discorso.pdf"]

    # Regenerating keeps the voice read from the documents.
    fake.answers.append(json.dumps({"posts": [POST]}))
    vctx.generator.regenerate(out["drafts"][0]["id"], "openai")
    assert "Parla al pubblico come ad amici" in fake.calls[1][1]


def test_reference_posts_with_a_saved_profile_and_through_chat(
    vctx: AppContext, fake: FakeProvider
) -> None:
    from taleport.voices.schemas import VoiceProfileIn

    profile = vctx.voices.create(VoiceProfileIn(name="Istituzionale", guide="- tono sobrio",
                                                examples=["Con orgoglio annunciamo"]))  # fmt: skip
    docs = [{"name": "a.pptx", "text": SPEECH}]
    fake.answers.append(json.dumps({"posts": [POST]}))
    out = vctx.generator.generate_from_reference(
        docs, ["instagram"], ["it"], voice="profile", voice_id=profile["id"], mode="openai"
    )
    prompt = fake.calls[0][1]
    assert "- tono sobrio" in prompt and "«Con orgoglio annunciamo»" in prompt
    assert out["voice_profile"] is None and out["voice"] is None

    handoff = vctx.generator.generate_from_reference(docs, ["instagram"], ["it"], mode="chat")
    assert "Daje Roma" in handoff["handoff"]["prompt"]
    pasted = vctx.generator.parse_reference(docs, ["instagram"], ["it"], json.dumps([POST]))
    assert pasted["drafts"][0]["text"].startswith("La Roma")

    with pytest.raises(AppError) as info:
        vctx.generator.generate_from_reference(docs, ["instagram", "linkedin"], ["it", "en"],
                                               count=4, mode="chat")  # fmt: skip
    assert info.value.code == "generator.too_many"
    with pytest.raises(AppError) as info:
        vctx.generator.generate_from_reference(docs, ["instagram"], ["it"], count=6, mode="chat")
    assert info.value.code == "generator.reference_count"
    with pytest.raises(AppError) as info:
        vctx.generator.generate_from_reference(docs, ["instagram"], ["it"], voice="profile")
    assert info.value.code == "validation"


def test_theme_and_long_content_use_the_chosen_profile(vctx: AppContext, fake) -> None:
    from taleport.voices.schemas import VoiceProfileIn

    profile = vctx.voices.create(VoiceProfileIn(name="Ironico", guide="- usa l'ironia"))
    _analysed_topic(vctx)
    theme = vctx.analysis.today_overview()["topics"][0]["themes"][0]
    post = {**POST, "platform": "linkedin", "language": "it"}
    fake.answers += [json.dumps({"posts": [post]}), json.dumps({"posts": [post]})]
    vctx.generator.generate_from_theme(theme["id"], ["linkedin"], ["it"], mode="openai",
                                       voice_id=profile["id"])  # fmt: skip
    assert "- usa l'ironia" in fake.calls[0][1]
    vctx.generator.generate_long(SPEECH, "Derby", 1, ["linkedin"], "it", mode="openai",
                                 voice_id=profile["id"])  # fmt: skip
    assert "- usa l'ironia" in fake.calls[1][1]


def test_reference_api(client: TestClient) -> None:
    body = {"documents": [{"name": "a.docx", "text": SPEECH}], "platforms": ["instagram"],
            "languages": ["it"], "mode": "chat"}  # fmt: skip
    out = client.post("/api/generator/reference", json=body).json()
    assert out["mode"] == "chat" and out["handoff"]["prompt"]
    parsed = client.post("/api/generator/reference/parse",
                         json={**body, "text": json.dumps({"posts": [POST]})}).json()  # fmt: skip
    assert parsed["drafts"][0]["origin"] == "long_content"
    analysis = client.post("/api/voices/analyze", json={"documents": body["documents"],
                                                        "mode": "chat"}).json()  # fmt: skip
    assert analysis["mode"] == "chat"


@pytest.mark.parametrize("language", ["it", "en", "es"])
@pytest.mark.parametrize("name", ["voice_analysis", "reference_posts"])
def test_voice_templates_render_fully(name: str, language: str) -> None:
    keys = ("documents", "audience", "tone", "style_examples", "count", "platforms", "languages")
    prompt = prompts.render(name, language, **{k: "x" for k in keys})
    assert "{{" not in prompt.system + prompt.user


def test_small_model_answers_are_repaired() -> None:
    """Real gemma3 answers: a list written without brackets and renamed keys."""
    from taleport.ai.structured import extract_json, repair_json
    from taleport.generator.service import ReferencePosts
    from taleport.voices.schemas import VoiceAnalysis

    broken = (
        '```json\n{"topics": ["Roma"], "voice": {"name": "Diretto",\n'
        '  "guide": "- Linguaggio semplice.",\n  "- Emozione.",\n  "- Daje Roma."\n'
        '  "- Niente dati."\n},\n'
        ' "posts": [{"platform": "instagram", "language": "it", "text": "Ciao \\"Roma\\"",'
        ' "hashtags": ["#a"],}]}\n```'
    )
    answer = ReferencePosts.model_validate(extract_json(broken))
    assert answer.voice.guide.splitlines() == [
        "- Linguaggio semplice.", "- Emozione.", "- Daje Roma.", "- Niente dati.",
    ]  # fmt: skip
    assert answer.posts[0].text == 'Ciao "Roma"'
    valid = '{"a": "x", "b": ["c", "d"], "e": {"f": "g, h"}}'
    assert repair_json(valid) == valid

    voice = VoiceAnalysis.model_validate({
        "name": "x", "guides": "- **Registro:** colloquiale\n- frasi brevi\n\n**Examples:**\n- a",
    })  # fmt: skip
    assert voice.guide == "- Registro: colloquiale\n- frasi brevi"
    wrapped = VoiceAnalysis.model_validate({"voice": {"istruzioni": ["tu", "frasi brevi ok"]}})
    assert wrapped.guide == "- tu\n- frasi brevi ok"
