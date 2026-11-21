"""LLM_SEED, X-Cache-Bypass and /api/retrieve (phase R4/R5: AD-38, architecture-a3 6.3)."""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.providers.llm.ollama import OllamaProvider
from app.schemas import Passage


def test_seed_setting_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_SEED", raising=False)
    assert get_settings().llm_seed is None
    monkeypatch.setenv("LLM_SEED", "42")
    assert get_settings().llm_seed == 42
    monkeypatch.setenv("LLM_SEED", "")
    assert get_settings().llm_seed is None


def _body(**kw) -> dict:
    seen = {}

    def h(req: httpx.Request) -> httpx.Response:
        seen.update(json.loads(req.content))
        return httpx.Response(200, json={"message": {"content": json.dumps({
            "reasoning": "r", "answer": "a", "citations": [], "answered_from_context": False, "confidence": "low"})}})

    p = OllamaProvider(Settings(llm_provider="ollama-host", ollama_url="http://o", **kw), transport=httpx.MockTransport(h))
    p.generate("q?", [Passage(chunk_id="c", text="t", source="s", section="1", score=0.9)])
    return seen


def test_seed_in_ollama_options_only_when_set() -> None:
    assert "seed" not in _body()["options"]
    assert _body(llm_seed=7)["options"]["seed"] == 7


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("RETRIEVER", "stub")
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_retrieve_returns_ranked_passages_without_a_model_call(client: TestClient) -> None:
    r = client.post("/api/retrieve", json={"question": "What is the attendance requirement?", "k": 2})
    assert r.status_code == 200
    body = r.json()
    assert [p["rank"] for p in body["retrieved"]] == [1, 2]
    assert {"chunk_id", "source", "section", "page", "score", "text"} <= set(body["retrieved"][0])
    assert body["scope"] == "current"


def test_retrieve_validates_input(client: TestClient) -> None:
    assert client.post("/api/retrieve", json={"question": "hi"}).status_code == 422
    assert client.post("/api/retrieve", json={"question": "valid question", "k": 0}).status_code == 422


def test_cache_bypass_header_reports_skip(client: TestClient) -> None:
    r = client.post("/api/ask", json={"question": "What is the attendance requirement?"},
                    headers={"X-Cache-Bypass": "1"})
    assert r.status_code == 200 and r.headers["X-Cache"] == "SKIP"
