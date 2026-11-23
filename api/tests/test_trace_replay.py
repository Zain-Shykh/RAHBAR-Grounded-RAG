"""The trace holds what produced the answer: the retry prompt (with its hint), every attempt, and a cache hit's
pointer to the request that made the stored answer. No network, no model."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.logjson import request_id_var
from app.providers.llm.base import InvalidModelOutput, ProviderError
from app.services import trace as tracemod
from app.services.answer import answer_question
from app.services.cache import MemoryCache
from tests.test_cache_answer import Q, ans, ret
from tests.test_answer import Scripted

S = Settings(relevance_floor=0.5, top_k=3)


@pytest.fixture()
def caught(monkeypatch):
    got: list[dict] = []
    monkeypatch.setattr(tracemod.Trace, "emit", lambda self: got.append(self.r))
    monkeypatch.setattr(tracemod, "embed_version", lambda model, url: f"{model}@test")
    return got


def test_retry_trace_has_both_attempts_and_the_final_prompt_has_the_hint(caught) -> None:
    out = answer_question(Q, ret(), Scripted(InvalidModelOutput("not json"), ans(1)), S)
    t = caught[0]
    assert out.outcome == "answered" and [a["attempt"] for a in t["attempt_log"]] == [1, 2]
    assert t["attempt_log"][0]["hint"] is None and t["attempt_log"][0]["result"] == "rejected: not json"
    assert t["attempt_log"][1]["result"] == "ok" and "not json" in t["prompt"][1]["content"]
    assert t["prompt_sha256"] == t["attempt_log"][1]["prompt_sha256"] != t["attempt_log"][0]["prompt_sha256"]
    assert t["prompt_sha256"] == tracemod.prompt_hash(t["prompt"])


def test_provider_error_is_recorded_per_attempt(caught) -> None:
    out = answer_question(Q, ret(), Scripted(ProviderError("boom", transient=False)), S)
    t = caught[0]
    assert out.outcome == "fallback" and t["attempt_log"][0]["result"].startswith("provider_error: boom")


def test_cache_hit_points_at_the_request_that_made_the_answer(caught) -> None:
    cache, r = MemoryCache(0.92), ret()
    token = request_id_var.set("req-1")
    answer_question(Q, r, Scripted(ans(1)), S, cache=cache)
    request_id_var.set("req-2")
    answer_question(Q, r, Scripted(), S, cache=cache)
    request_id_var.reset(token)
    assert caught[1]["cache"] == "hit" and caught[1]["cached_from"] == "req-1" and caught[1]["prompt"] is None
