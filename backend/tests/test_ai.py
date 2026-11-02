"""AI layer: prompts, JSON validation, providers' HTTP shapes, features and fallbacks."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from taleport.ai import prompts
from taleport.ai.handoff import build_handoff
from taleport.ai.providers.anthropic_provider import AnthropicProvider
from taleport.ai.providers.base import Completion, ProviderError
from taleport.ai.providers.ollama import OllamaProvider
from taleport.ai.providers.openai_compat import ChatCompletionsProvider, ResponsesProvider
from taleport.ai.registry import build_provider, provider_status
from taleport.ai.schemas import ThemeInsights
from taleport.ai.structured import extract_json, parse_answer, run_structured
from taleport.ai.usage import estimate_cost
from taleport.api.context import AppContext, build_context
from taleport.core.errors import AppError
from taleport.core.secrets import SecretStore
from taleport.core.settings import AppSettings
from taleport.db.database import Database
from tests.conftest import TEST_TOKEN, topic_payload
from tests.test_analysis import STORIES


class FakeProvider:
    name = "openai"
    model = "gpt-6-sol"
    paid = True

    def __init__(self, answers: list[str]) -> None:
        self.answers = list(answers)
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str, *, json_output: bool, max_tokens: int = 0):
        self.calls.append((system, user))
        return Completion(
            text=self.answers.pop(0), model=self.model, input_tokens=1000, output_tokens=500
        )


# -- prompts & JSON --------------------------------------------------------------------


@pytest.mark.parametrize("language", ["it", "en", "es"])
@pytest.mark.parametrize("name", ["theme_insights", "topic_suggestion", "x_search"])
def test_every_template_renders_fully(name: str, language: str) -> None:
    values = {k: "x" for k in ("topic_name", "topic_description", "topic_audience", "themes",
                               "description", "languages", "days", "query", "context")}  # fmt: skip
    prompt = prompts.render(name, language, **values)
    assert prompt.version >= 1 and prompt.system and prompt.user
    assert "{{" not in prompt.system + prompt.user
    assert prompts.LANGUAGE_NAMES[language][language] in prompt.system + prompt.user


def test_extract_json_tolerates_fences_and_chatter() -> None:
    assert extract_json('Ecco:\n```json\n{"a": 1}\n```\nfine') == {"a": 1}
    assert extract_json('Sure! {"themes": []} Hope it helps') == {"themes": []}
    with pytest.raises(ValueError):
        extract_json("nessun json qui")


def test_parse_pasted_answer_reports_a_clear_error() -> None:
    with pytest.raises(AppError) as info:
        parse_answer('{"themes": [{"title": "senza id"}]}', ThemeInsights)
    assert info.value.code == "ai.invalid_pasted" and "id" in info.value.params["detail"]


def test_run_structured_retries_once_then_fails_clearly() -> None:
    prompt = prompts.render("theme_insights", "it", themes="-", topic_name="t",
                            topic_description="-", topic_audience="-")  # fmt: skip
    recorded: list[Completion] = []
    good = '{"themes": [{"id": 1, "title": "Titolo"}]}'

    provider = FakeProvider(["non è json", good])
    result = run_structured(provider, prompt, ThemeInsights, recorded.append)
    assert result.themes[0].title == "Titolo"
    assert len(provider.calls) == 2 and "JSON" in provider.calls[1][1]
    assert len(recorded) == 2

    with pytest.raises(AppError) as info:
        run_structured(FakeProvider(["no", "ancora no"]), prompt, ThemeInsights, recorded.append)
    assert info.value.code == "ai.invalid_response"


def test_handoff_prefill_is_opt_in_and_length_limited() -> None:
    assert build_handoff("claude", "ciao", prefill=False).url == "https://claude.ai/new"
    short = build_handoff("grok", "ciao mondo", prefill=True)
    assert short.prefilled and short.url == "https://grok.com/?q=ciao%20mondo"
    long = build_handoff("chatgpt", "x" * 5000, prefill=True)
    assert not long.prefilled and long.url == "https://chatgpt.com/"


def test_cost_estimates() -> None:
    assert estimate_cost("claude-opus-5-5", 1_000_000, 0) == pytest.approx(4.0)
    assert estimate_cost("gpt-6-sol", 500_000, 100_000) == pytest.approx(2.0)
    assert estimate_cost("modello-sconosciuto", 10, 10) is None


# -- providers (HTTP shapes) -------------------------------------------------------------


@respx.mock
def test_chat_completions_provider() -> None:
    route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={
            "model": "gpt-6-sol",
            "choices": [{"message": {"content": '{"ok": true}'}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 3},
        })
    )  # fmt: skip
    provider = ChatCompletionsProvider(
        "openai", "OpenAI", "https://api.openai.com/v1", "k", "gpt-6-sol"
    )
    completion = provider.complete("sys", "user", json_output=True)
    body = json.loads(route.calls[0].request.content)
    assert body["response_format"] == {"type": "json_object"}
    assert "temperature" not in body and body["max_completion_tokens"] > 0
    assert route.calls[0].request.headers["Authorization"] == "Bearer k"
    assert (completion.text, completion.input_tokens, completion.output_tokens) == (
        '{"ok": true}',
        12,
        3,
    )

    respx.post("https://api.openai.com/v1/chat/completions").mock(return_value=httpx.Response(401))
    with pytest.raises(ProviderError) as info:
        provider.complete("s", "u", json_output=False)
    assert info.value.code == "ai.key_invalid"


@respx.mock
def test_responses_provider_reads_text_citations_and_cost() -> None:
    respx.post("https://api.perplexity.ai/v1/agent").mock(
        return_value=httpx.Response(200, json={
            "model": "perplexity/sonar",
            "output": [{"type": "message", "content": [{
                "type": "output_text", "text": "Risposta",
                "annotations": [{"type": "url_citation", "url": "https://x.com/a/status/1"}],
            }]}],
            "usage": {"input_tokens": 100, "output_tokens": 20, "cost": {"total_cost": 0.0123}},
        })
    )  # fmt: skip
    provider = ResponsesProvider("perplexity", "Perplexity", "https://api.perplexity.ai/v1/agent",
                                 "k", "perplexity/sonar")  # fmt: skip
    completion = provider.complete("istruzioni", "domanda", json_output=True)
    assert completion.text == "Risposta"
    assert completion.citations == ["https://x.com/a/status/1"]
    assert completion.cost_usd == pytest.approx(0.0123)


@respx.mock
def test_ollama_provider_and_unreachable() -> None:
    route = respx.post("http://localhost:11434/api/chat").mock(
        return_value=httpx.Response(200, json={
            "message": {"content": "{}"}, "prompt_eval_count": 50, "eval_count": 10,
        })
    )  # fmt: skip
    completion = OllamaProvider("llama3.2").complete("s", "u", json_output=True)
    assert json.loads(route.calls[0].request.content)["format"] == "json"
    assert completion.input_tokens == 50 and completion.cost_usd == 0.0

    respx.post("http://localhost:11434/api/chat").mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(ProviderError) as info:
        OllamaProvider("llama3.2").complete("s", "u", json_output=True)
    assert info.value.code == "ai.ollama_unreachable"


def test_anthropic_provider_uses_fallbacks_and_handles_refusal() -> None:
    calls: list[dict] = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            stop_reason="end_turn",
            model=kwargs["model"],
            content=[
                SimpleNamespace(type="thinking"),
                SimpleNamespace(type="text", text='{"a":1}'),
            ],
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )

    provider = AnthropicProvider("sk-test", "claude-opus-5-5")
    provider._client = SimpleNamespace(
        beta=SimpleNamespace(messages=SimpleNamespace(create=create))
    )
    completion = provider.complete("sys", "user", json_output=True)
    assert completion.text == '{"a":1}'
    assert calls[0]["fallbacks"] == "default"
    assert calls[0]["betas"] == ["server-side-fallback-2026-07-01"]
    assert "temperature" not in calls[0]

    def refuse(**kwargs):
        return SimpleNamespace(stop_reason="refusal", content=[], model="x", usage=None)

    provider._client = SimpleNamespace(
        beta=SimpleNamespace(messages=SimpleNamespace(create=refuse))
    )
    with pytest.raises(ProviderError) as info:
        provider.complete("s", "u", json_output=False)
    assert info.value.code == "ai.refused"


def test_registry_needs_keys() -> None:
    settings = AppSettings()
    with pytest.raises(ProviderError) as info:
        build_provider("openai", settings, SecretStore())
    assert info.value.code == "ai.no_key"
    assert provider_status("anthropic", settings, SecretStore())["code"] == "ai.no_key"
    SecretStore().set("anthropic", "sk-test")
    status = provider_status("anthropic", settings, SecretStore())
    assert status["ready"] and status["model"] == "claude-opus-5-5"


# -- features ------------------------------------------------------------------------


@pytest.fixture
def fake_provider() -> FakeProvider:
    return FakeProvider([])


@pytest.fixture
def ai_ctx(db: Database, fake_provider: FakeProvider) -> AppContext:
    def factory(mode, settings, secrets):
        if mode == "anthropic":
            raise ProviderError("ai.no_key", provider="Anthropic")
        return fake_provider

    return build_context(db, TEST_TOKEN, collectors_factory=lambda: [], ai_provider_factory=factory)


def test_topic_suggestion_with_provider_chat_and_fallback(
    ai_ctx: AppContext, fake_provider
) -> None:
    fake_provider.answers.append(json.dumps({
        "name": "AI nel marketing", "description": "d",
        "keywords": {"it": ["intelligenza artificiale"], "en": ["ai marketing"], "es": ["ia"]},
        "platforms": ["linkedin", "myspace"],
        "sources": [{"kind": "subreddit", "value": "marketing"}, {"kind": "blog", "value": "x"}],
        "extra_field": "ignored",
    }))  # fmt: skip
    out = ai_ctx.ai.suggest_topic("AI per PMI", ["it-IT", "en-US"], "openai")
    assert out["mode"] == "openai"
    assert set(out["result"]["keywords"]) == {"it", "en"}  # only the chosen languages
    assert out["result"]["platforms"] == ["linkedin"]
    assert out["result"]["sources"] == [{"kind": "subreddit", "value": "marketing"}]
    assert ai_ctx.usage.recent()[0]["feature"] == "topic_suggestion"
    assert ai_ctx.usage.month_total() > 0

    chat = ai_ctx.ai.suggest_topic("AI per PMI", ["it-IT"], "chat")
    assert chat["handoff"]["url"] == "https://claude.ai/new" and chat["handoff"]["copied"]
    assert "AI per PMI" in chat["handoff"]["prompt"]

    fallback = ai_ctx.ai.suggest_topic("AI per PMI", ["it-IT"], "anthropic")
    assert fallback["mode"] == "chat" and fallback["fallback"] == "ai.no_key"

    pasted = ai_ctx.ai.parse_topic_suggestion('```json\n{"name": "Da chat"}\n```', ["it-IT"])
    assert pasted["result"]["name"] == "Da chat"


def _analysed_topic(ctx: AppContext) -> int:
    topic = ctx.topics.create(
        topic_payload(editions=["en-US"], keywords={"en": ["social media marketing"]}, hashtags=[])
    )
    ctx.items.save(STORIES, topic.id, None)
    ctx.analysis.analyze(topic.id)
    return topic.id


def test_theme_insights_apply_titles_and_merge(ai_ctx: AppContext, fake_provider) -> None:
    topic_id = _analysed_topic(ai_ctx)
    themes = ai_ctx.analysis.today_overview()["topics"][0]["themes"]
    assert len(themes) >= 2
    first, second = themes[0]["id"], themes[1]["id"]
    fake_provider.answers.append(json.dumps({"themes": [
        {"id": first, "title": "Titolo AI", "summary": "Riassunto.", "angle": "Angolo."},
        {"id": second, "title": "Doppione", "same_as": first},
        {"id": 99999, "title": "Inventato"},
    ]}))  # fmt: skip

    out = ai_ctx.ai.theme_insights(topic_id, "openai")
    assert out["updated"] == 2
    detail = ai_ctx.analysis.theme_detail(first)
    assert (detail["title"], detail["summary"], detail["angle"], detail["origin"]) == (
        "Titolo AI", "Riassunto.", "Angolo.", "ai")  # fmt: skip
    assert detail["item_count"] == themes[0]["item_count"] + themes[1]["item_count"]
    with pytest.raises(AppError):
        ai_ctx.analysis.theme_detail(second)

    # A later re-analysis the same day keeps what the AI wrote.
    ai_ctx.analysis.analyze(topic_id)
    titles = [t["title"] for t in ai_ctx.analysis.today_overview()["topics"][0]["themes"]]
    assert "Titolo AI" in titles

    # The prompt sent to the AI lists the themes with their items.
    assert "[news]" in fake_provider.calls[0][1] and f"id {first}" in fake_provider.calls[0][1]


def test_theme_insights_from_pasted_answer(ai_ctx: AppContext) -> None:
    topic_id = _analysed_topic(ai_ctx)
    theme_id = ai_ctx.analysis.today_overview()["topics"][0]["themes"][0]["id"]
    handoff = ai_ctx.ai.theme_insights(topic_id, "chat")["handoff"]
    assert f"id {theme_id}" in handoff["prompt"]
    answer = json.dumps({"themes": [{"id": theme_id, "title": "Dalla chat"}]})
    text = f"Ecco il risultato:\n```json\n{answer}\n```"
    assert ai_ctx.ai.parse_theme_insights(topic_id, text)["updated"] == 1
    assert ai_ctx.analysis.theme_detail(theme_id)["title"] == "Dalla chat"


def test_x_search_chat_and_api(ai_ctx: AppContext) -> None:
    topic_id = _analysed_topic(ai_ctx)
    theme_id = ai_ctx.analysis.today_overview()["topics"][0]["themes"][0]["id"]

    handoff = ai_ctx.ai.x_search(theme_id, None, "chat")["handoff"]
    assert handoff["site"] == "grok" and handoff["url"] == "https://grok.com/"
    assert "X" in handoff["prompt"]

    ai_ctx.ai.save_x_report(
        theme_id, None, "Su X si parla molto di Advantage Plus. https://x.com/a/status/1"
    )
    reports = ai_ctx.analysis.theme_detail(theme_id)["x_reports"]
    assert reports[0]["via"] == "chat" and "Advantage Plus" in reports[0]["text"]

    captured = {}

    class FakeX:
        name, model, paid = "xai", "grok-4.7", True

        def complete(self, system, user, *, json_output, max_tokens=0):
            return Completion(
                text="Report API",
                model="grok-4.7",
                input_tokens=10,
                output_tokens=10,
                citations=["https://x.com/b/status/2"],
            )

    def x_factory(settings, secrets, from_date, to_date):
        captured.update(from_date=from_date, to_date=to_date)
        return FakeX()

    ai_ctx.ai._x_factory = x_factory
    ai_ctx.ai.x_search(None, topic_id, "xai")
    assert captured["from_date"] < captured["to_date"]
    assert ai_ctx.usage.recent()[0]["feature"] == "x_search"

    # The X report survives a re-analysis of the day.
    ai_ctx.analysis.analyze(topic_id)
    new_first = ai_ctx.analysis.today_overview()["topics"][0]["themes"][0]["id"]
    assert ai_ctx.analysis.theme_detail(new_first)["x_reports"]


def test_ai_api(client: TestClient, ctx: AppContext) -> None:
    data = client.get("/api/ai/providers").json()
    assert [p["id"] for p in data["providers"]] == [
        "ollama", "anthropic", "openai", "xai", "perplexity", "gemini"]  # fmt: skip
    assert data["default"] == "chat"
    response = client.post("/api/ai/topic-suggestion", json={"description": "Moda sostenibile"})
    assert response.json()["handoff"]["copied"] is True
    assert client.post("/api/ai/theme-insights", json={"topic_id": 999}).status_code == 404
    assert client.post("/api/ai/providers/nope/test").status_code == 404
    assert client.get("/api/status").json()["api_spend_month"] == 0
