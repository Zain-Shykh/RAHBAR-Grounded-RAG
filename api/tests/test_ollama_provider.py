"""OllamaProvider against a mock transport: no network, no model."""

from __future__ import annotations

import json
import threading
import time

import httpx
import pytest

from app.config import Settings
from app.providers.llm import get_provider
from app.providers.llm.base import InvalidModelOutput, ProviderError
from app.providers.llm.ollama import OllamaProvider
from app.schemas import Answer, Passage

P = [Passage(chunk_id="c1", text="Attendance is 80%.", source="a.pdf", section="1.1", page=2, score=0.9)]
GOOD = {"reasoning": "r", "answer": "80%", "citations": [{"source": "a.pdf", "section": "1.1", "page": 2}],
        "answered_from_context": True, "confidence": "high"}


def provider(handler, **kw) -> OllamaProvider:
    s = Settings(llm_provider="ollama-host", ollama_url="http://o:11434", **kw)
    return OllamaProvider(s, transport=httpx.MockTransport(handler))


def ok(req: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"message": {"content": json.dumps(GOOD)},
                                     "prompt_eval_count": 11, "eval_count": 7})


def test_request_body_and_tokens() -> None:
    seen = {}

    def h(req: httpx.Request) -> httpx.Response:
        seen["url"], seen["body"] = str(req.url), json.loads(req.content)
        return ok(req)

    res = provider(h, temperature=0.1, llm_num_ctx=4096, llm_max_tokens=99).generate("q?", P)
    b = seen["body"]
    assert seen["url"] == "http://o:11434/api/chat"
    assert b["stream"] is False and b["model"] == "llama3.2:3b"
    assert b["format"] == Answer.model_json_schema()
    assert b["options"] == {"temperature": 0.1, "num_ctx": 4096, "num_predict": 99}
    assert b["messages"][0]["role"] == "system" and "<<<EVIDENCE 1" in b["messages"][1]["content"]
    assert (res.tokens_in, res.tokens_out) == (11, 7) and res.answer.answer == "80%"


def test_hint_reaches_the_prompt() -> None:
    seen = {}

    def h(req: httpx.Request) -> httpx.Response:
        seen["u"] = json.loads(req.content)["messages"][1]["content"]
        return ok(req)

    provider(h).generate("q?", P, hint="Your previous reply was invalid because: schema.")
    assert "previous reply was invalid" in seen["u"]


def test_missing_token_counts_are_zero() -> None:
    def h(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": json.dumps(GOOD)}})

    res = provider(h).generate("q?", P)
    assert (res.tokens_in, res.tokens_out) == (0, 0)


@pytest.mark.parametrize("exc", [httpx.ReadTimeout("t"), httpx.ConnectError("c"),
                                 httpx.ReadError("r"), httpx.RemoteProtocolError("p")])
def test_transient_errors(exc: Exception) -> None:
    def h(req: httpx.Request) -> httpx.Response:
        raise exc

    with pytest.raises(ProviderError) as e:
        provider(h).generate("q?", P)
    assert e.value.transient is True


def test_http_error_is_not_transient() -> None:
    with pytest.raises(ProviderError) as e:
        provider(lambda r: httpx.Response(500, text="boom")).generate("q?", P)
    assert e.value.transient is False


@pytest.mark.parametrize("payload", [{"nope": 1}, {"message": {}}, {"message": None}, []])
def test_bad_envelope_is_provider_error(payload) -> None:
    with pytest.raises(ProviderError) as e:
        provider(lambda r: httpx.Response(200, json=payload)).generate("q?", P)
    assert e.value.transient is False


def test_non_json_body_is_provider_error() -> None:
    with pytest.raises(ProviderError):
        provider(lambda r: httpx.Response(200, text="<html>")).generate("q?", P)


@pytest.mark.parametrize("content,reason", [("I think the answer is 80%", "not_json"),
                                            ('{"answer": "x"}', "schema"), (None, "not_json")])
def test_bad_model_content_is_invalid_output(content, reason) -> None:
    def h(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": content}})

    with pytest.raises(InvalidModelOutput) as e:
        provider(h).generate("q?", P)
    assert e.value.reason == reason


def test_semaphore_limits_concurrency() -> None:
    cur = peak = 0
    lock = threading.Lock()

    def h(req: httpx.Request) -> httpx.Response:
        nonlocal cur, peak
        with lock:
            cur += 1
            peak = max(peak, cur)
        time.sleep(0.05)
        with lock:
            cur -= 1
        return ok(req)

    p = provider(h, llm_max_concurrency=2)
    ts = [threading.Thread(target=p.generate, args=("q?", P)) for _ in range(6)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert peak == 2


def test_busy_slot_times_out_without_a_call() -> None:
    calls: list[int] = []

    def h(req: httpx.Request) -> httpx.Response:
        calls.append(1)
        return ok(req)

    p = provider(h, llm_max_concurrency=1, llm_timeout_seconds=0)
    assert p._sem.acquire()
    with pytest.raises(ProviderError) as e:
        p.generate("q?", P)
    assert e.value.transient is False and not calls


def test_slot_is_released_after_an_error() -> None:
    p = provider(lambda r: httpx.Response(500), llm_max_concurrency=1, llm_timeout_seconds=1)
    for _ in range(3):
        with pytest.raises(ProviderError):
            p.generate("q?", P)


def test_get_provider_builds_ollama() -> None:
    for name in ("ollama-host", "ollama-incluster"):
        prov = get_provider(Settings(llm_provider=name))
        assert isinstance(prov, OllamaProvider) and prov.name == name


def test_hosted_is_a_clear_config_error() -> None:
    with pytest.raises(ValueError, match="hosted.*not implemented"):
        get_provider(Settings(llm_provider="hosted"))
    with pytest.raises(ValueError, match="unknown LLM_PROVIDER"):
        get_provider(Settings(llm_provider="nope"))
