"""AI failures must reach the user as clear messages, and imperfect answers should still work.

Regression for 1.1.0: an Ollama HTTP 500 turned into "internal error" because the provider's
`status` param clashed with AppError's own `status` argument.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from taleport.ai import prompts
from taleport.ai.providers.base import Completion, ProviderError
from taleport.ai.providers.ollama import OllamaProvider
from taleport.ai.providers.openai_compat import ChatCompletionsProvider
from taleport.ai.structured import run_structured
from taleport.api.context import build_context
from taleport.core.errors import AppError
from taleport.db.database import Database
from taleport.generator.schemas import GeneratedPosts
from tests.conftest import TEST_TOKEN

OLLAMA = "http://localhost:11434/api/chat"
OK = {"message": {"content": '{"posts": []}'}, "prompt_eval_count": 1, "eval_count": 1}


def test_provider_errors_convert_without_clashing() -> None:
    exc = ProviderError("ai.provider_error", provider="Ollama", status=500)
    error = AppError.from_provider(exc)
    assert error.status == 502
    assert error.params == {"provider": "Ollama", "http_status": 500}
    assert error.to_payload()["error"]["code"] == "ai.provider_error"


@respx.mock
def test_ollama_retries_without_json_mode_after_a_server_error() -> None:
    route = respx.post(OLLAMA).mock(
        side_effect=[httpx.Response(500, json={"error": "boom"}), httpx.Response(200, json=OK)]
    )
    OllamaProvider("gemma3").complete("s", "u", json_output=True)
    first, second = (json.loads(c.request.content) for c in route.calls)
    assert first["format"] == "json" and "format" not in second
    assert first["options"]["temperature"] == 0.4


@respx.mock
def test_ollama_errors_are_specific() -> None:
    respx.post(OLLAMA).mock(return_value=httpx.Response(500, json={"error": "boom"}))
    with pytest.raises(ProviderError) as info:
        OllamaProvider("gemma3").complete("s", "u", json_output=True)
    assert info.value.code == "ai.provider_error" and info.value.params["http_status"] == 500

    respx.post(OLLAMA).mock(
        return_value=httpx.Response(500, json={"error": "model requires more system memory"})
    )
    with pytest.raises(ProviderError) as info:
        OllamaProvider("gemma3").complete("s", "u", json_output=False)
    assert info.value.code == "ai.ollama_memory"


@respx.mock
def test_generation_with_a_failing_ollama_shows_a_real_error(db: Database) -> None:
    respx.post(OLLAMA).mock(return_value=httpx.Response(500, json={"error": "boom"}))
    ctx = build_context(
        db, TEST_TOKEN, collectors_factory=list,
        ai_provider_factory=lambda *_: OllamaProvider("gemma3"), start_video_worker=False,
    )  # fmt: skip
    with pytest.raises(AppError) as info:
        ctx.generator._run(prompts.render("long_content", "it"), "ollama", "generate")
    assert info.value.code == "ai.provider_error" and info.value.status == 502


@respx.mock
def test_openai_without_credit_is_not_called_rate_limited() -> None:
    provider = ChatCompletionsProvider("openai", "OpenAI", "https://api.openai.com/v1", "k", "m")
    quota = {"error": {"message": "You exceeded your current quota", "type": "insufficient_quota",
                       "code": "insufficient_quota"}}  # fmt: skip
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(429, json=quota)
    )
    with pytest.raises(ProviderError) as info:
        provider.complete("s", "u", json_output=True)
    assert info.value.code == "ai.no_credit"

    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(429, json={"error": {"message": "Rate limit reached"}})
    )
    with pytest.raises(ProviderError) as info:
        provider.complete("s", "u", json_output=True)
    assert info.value.code == "ai.rate_limited"


def test_posts_schema_accepts_imperfect_answers() -> None:
    sloppy = [
        {
            "platform": "Instagram", "language": "IT", "variant": "2",
            "hashtags": "#roma #calcio, #asroma",
            "carousel": [{"titolo": "Slide 1", "testo": "Ciao"}, "Slide 2"],
            "script": ["Apri con il gol", {"time": 3, "voiceover": ["Forza", "Roma"]}],
            "text": ["Prima riga", "Seconda riga"],
            "series_index": 99,
        }
    ]  # fmt: skip
    posts = GeneratedPosts.model_validate(sloppy).posts
    post = posts[0]
    assert (post.platform, post.language, post.variant, post.series_index) == (
        "instagram", "it", 2, 50,
    )  # fmt: skip
    assert post.hashtags == ["roma", "calcio", "asroma"]
    assert post.carousel == ["Slide 1 — Ciao", "Slide 2"]
    assert post.script[0].voiceover == "Apri con il gol" and post.script[1].time == "3"
    assert post.text == "Prima riga\nSeconda riga"
    single = GeneratedPosts.model_validate({"platform": "x", "language": "it", "text": "t"})
    assert len(single.posts) == 1
    nested = GeneratedPosts.model_validate({"bozze": [{"platform": "x", "language": "it"}]})
    assert nested.posts[0].platform == "x"


class _Local:
    name, model, paid = "ollama", "gemma3", False

    def __init__(self, answers: list[str]) -> None:
        self.answers = answers

    def complete(self, system, user, *, json_output, max_tokens=0, images=None):
        return Completion(text=self.answers.pop(0), model=self.model)


def test_local_models_get_one_more_corrective_try() -> None:
    good = json.dumps({"posts": [{"platform": "x", "language": "it", "text": "ok"}]})
    provider = _Local(["non è json", "{}", good])
    result = run_structured(provider, prompts.render("long_content", "it"), GeneratedPosts,
                            lambda _c: None)  # fmt: skip
    assert result.posts[0].text == "ok"
