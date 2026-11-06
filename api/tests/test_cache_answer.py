"""The cache inside the query pipeline and /readyz (AC-1, 2, 3, 5, 6, 7). Fakes only."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

import pytest
import redis
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from app.config import Settings
from app.embedding import EmbedError
from app.logjson import request_id_var
from app.providers.llm.base import InvalidModelOutput, ProviderError
from app.retrieval.chroma import ChromaRetriever
from app.services.answer import answer_question
from app.services.cache import MemoryCache, SemanticCache
from app.services.index_state import IndexState
from tests.fakes import FakeClient, FakeCollection, meta, rows
from tests.test_answer import FakeRetriever, P, Scripted, ans, counter
from tests.test_cache import FakeRedis

S = Settings(relevance_floor=0.5, top_k=3)
Q = "What is the attendance rule?"


class Emb:
    model = "m"

    def __init__(self, vec: list[float] | None = None) -> None:
        self.vec = vec or [1.0, 0.0, 0.0]
        self.calls = 0

    def embed_query(self, question: str) -> list[float]:
        self.calls += 1
        return self.vec


class State:
    """What answer_question needs of IndexState: a snapshot with the live index_id."""

    def __init__(self, index_id: str = "i1", versions: list[str] | None = None) -> None:
        self.snap = SimpleNamespace(index_id=index_id, dimension=3, embed_model="m", chunk_count=2,
                                    doc_versions=versions or ["2023-08", "2026-06"])

    def get(self) -> Any:
        return self.snap

    def require_pin(self, snap: Any) -> None:
        pass


def ret(passages=None, *, state: State | None = None, emb: Emb | None = None) -> FakeRetriever:
    return FakeRetriever(passages if passages is not None else [P(1)], embedder=emb or Emb(),
                         state=state or State())


def ask(retriever, provider, cache, q: str = Q, **kw):
    return answer_question(q, retriever, provider, S, cache=cache, **kw)


# -- AC-1: MISS then HIT, fresh request id -----------------------------------------------------

def test_second_call_is_a_hit_with_fresh_request_id() -> None:
    cache, r, prov = MemoryCache(0.92), ret(), Scripted(ans(1))
    token = request_id_var.set("req-1")
    first = ask(r, prov, cache)
    request_id_var.set("req-2")
    second = ask(r, prov, cache)
    request_id_var.reset(token)
    assert (first.cache, first.outcome) == ("MISS", "answered")
    assert (second.cache, second.outcome) == ("HIT", "cached")
    assert len(prov.calls) == 1 and len(r.calls) == 1           # no retrieval, no model on the hit
    assert second.response.answer == first.response.answer
    assert second.response.citations == first.response.citations
    assert (first.response.request_id, second.response.request_id) == ("req-1", "req-2")


def test_hit_log_line(caplog) -> None:
    cache, r = MemoryCache(0.92), ret()
    ask(r, Scripted(ans(1)), cache)
    with caplog.at_level(logging.INFO, logger="rahbar.answer"):
        ask(r, Scripted(), cache)
    rec = [x for x in caplog.records if x.message == "answered"][-1]
    assert (rec.cache, rec.outcome, rec.ms_retrieve, rec.ms_generate) == ("hit", "cached", 0.0, 0.0)  # type: ignore[attr-defined]


def test_miss_log_line(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="rahbar.answer"):
        ask(ret(), Scripted(ans(1)), MemoryCache())
    assert [x for x in caplog.records if x.message == "answered"][-1].cache == "miss"  # type: ignore[attr-defined]


def test_a_dissimilar_question_misses() -> None:
    cache, prov = MemoryCache(0.92), Scripted(ans(1), ans(1))
    ask(ret(emb=Emb([1.0, 0.0, 0.0])), prov, cache)
    r = ask(ret(emb=Emb([0.0, 1.0, 0.0])), prov, cache)
    assert r.cache == "MISS" and len(prov.calls) == 2


# -- AC-2: scope isolation ---------------------------------------------------------------------

def test_scope_isolation() -> None:
    cache, prov, r = MemoryCache(0.9), Scripted(ans(1), ans(1), ans(1)), ret()
    a = ask(r, prov, cache, "What is the withdrawal deadline in 2026?")
    b = ask(r, prov, cache, "What is the withdrawal deadline in 2023?")     # same vector, other scope
    c = ask(r, prov, cache, "What is the withdrawal deadline in 2026?")
    assert (a.cache, b.cache, c.cache) == ("MISS", "MISS", "HIT") and len(prov.calls) == 2


# -- AC-3: never cache what must not be cached -------------------------------------------------

def test_unsafe_outcomes_are_not_stored() -> None:
    cases = {
        "below_floor": (ret([P(1, 0.2)]), Scripted()),
        "model_abstains": (ret(), Scripted(ans(1, yes=False, cite=False))),
        "fallback_invalid": (ret(), Scripted(InvalidModelOutput("a"), InvalidModelOutput("b"))),
        "fallback_citation": (ret(), Scripted(ans(9), ans(9))),
        "fallback_provider": (ret(), Scripted(ProviderError("x"), ProviderError("x"))),
    }
    for name, (r, prov) in cases.items():
        cache = MemoryCache(0.5)
        first = ask(r, prov, cache)
        assert first.outcome in ("abstained", "fallback"), name
        again = ask(r, Scripted(*([ans(1)] * 3)), cache)
        assert again.cache == "MISS", f"{name} was cached"


def test_embedding_failure_is_a_fallback_and_never_stored() -> None:
    class Bad(Emb):
        def embed_query(self, question: str) -> list[float]:
            raise EmbedError("down")

    cache = MemoryCache(0.5)
    r = ask(ret(emb=Bad()), Scripted(), cache)
    assert r.outcome == "fallback" and r.cache == "SKIP"
    assert cache._entries == {} or all(not v for v in cache._entries.values())


def test_follow_up_neither_reads_nor_writes() -> None:
    cache, r, prov = MemoryCache(0.9), ret(), Scripted(ans(1), ans(1))
    ask(r, prov, cache)                                         # stored
    f = ask(r, prov, cache, follow_up=True)
    assert f.cache == "SKIP" and f.outcome == "answered" and len(prov.calls) == 2
    fresh = MemoryCache(0.9)
    ask(r, Scripted(ans(1)), fresh, follow_up=True)
    assert ask(r, Scripted(ans(1)), fresh).cache == "MISS"      # the follow-up wrote nothing


def test_no_cache_or_no_vector_is_skip() -> None:
    assert ask(ret(), Scripted(ans(1)), None).cache == "SKIP"
    stub = FakeRetriever([P(1)])                                # no embedder, no state: stub mode
    assert ask(stub, Scripted(ans(1)), MemoryCache()).cache == "SKIP"


# -- AC-4: index_id is in the key --------------------------------------------------------------

def test_a_new_index_id_never_returns_the_old_answer() -> None:
    cache, state, prov = MemoryCache(0.9), State("old"), Scripted(ans(1), ans(1))
    r = ret(state=state)
    assert ask(r, prov, cache).cache == "MISS"
    assert ask(r, prov, cache).cache == "HIT"
    state.snap.index_id = "new"                                 # the indexer swapped the collection
    assert ask(r, prov, cache).cache == "MISS" and len(prov.calls) == 2


# -- AC-5: Redis down ---------------------------------------------------------------------------

def test_redis_down_still_answers(caplog) -> None:
    fake = FakeRedis()
    fake.error = redis.ConnectionError("refused")
    cache = SemanticCache(fake, 0.92, 60)
    with caplog.at_level(logging.WARNING):
        r = ask(ret(), Scripted(ans(1)), cache)
    assert r.outcome == "answered" and r.cache == "MISS" and r.response.answered_from_context
    assert any("cache unavailable" in x.message for x in caplog.records)


def test_redis_dies_between_lookup_and_store() -> None:
    fake = FakeRedis()
    cache = SemanticCache(fake, 0.92, 60)

    class Dies(Scripted):
        def generate(self, *a: Any, **k: Any):
            fake.error = redis.ConnectionError("gone")
            return super().generate(*a, **k)

    assert ask(ret(), Dies(ans(1)), cache).outcome == "answered"


# -- AC-7: metrics -------------------------------------------------------------------------------

def test_cache_metrics() -> None:
    h0, m0 = counter("rahbar_cache_lookups_total", result="hit"), counter("rahbar_cache_lookups_total", result="miss")
    cache, r, prov = MemoryCache(0.9), ret(), Scripted(ans(1))
    ask(r, prov, cache)
    ask(r, prov, cache)
    ask(r, prov, cache, follow_up=True)                         # SKIP is not a lookup
    assert counter("rahbar_cache_lookups_total", result="hit") == h0 + 1
    assert counter("rahbar_cache_lookups_total", result="miss") == m0 + 1
    ratio = REGISTRY.get_sample_value("rahbar_cache_hit_ratio")
    assert ratio is not None and 0.0 <= ratio <= 1.0


# -- the route: headers ---------------------------------------------------------------------------

def test_route_headers_hit_and_miss(monkeypatch) -> None:
    monkeypatch.setenv("RETRIEVER", "stub")
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    from app.main import app

    with TestClient(app) as c:
        app.state.retriever, app.state.provider = ret(), Scripted(ans(1))
        app.state.cache = MemoryCache(0.9)
        a = c.post("/api/ask", json={"question": Q})
        b = c.post("/api/ask", json={"question": Q})
    assert (a.headers["x-cache"], a.headers["x-outcome"]) == ("MISS", "answered")
    assert (b.headers["x-cache"], b.headers["x-outcome"]) == ("HIT", "cached")
    assert a.json()["request_id"] != b.json()["request_id"]
    assert a.json()["answer"] == b.json()["answer"]


# -- AC-6: /readyz ----------------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def fresh_probe_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.routes.health as health

    monkeypatch.setattr(health, "_job", None)


def readyz(monkeypatch, cache, fake: FakeClient | None = None):
    monkeypatch.setenv("RETRIEVER", "stub")
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    from app.main import app

    s = Settings(embed_model="hashing-bow-768", index_refresh_seconds=0)
    state = IndexState(s, client=fake or FakeClient(FakeCollection(rows(), meta(index_id="idx-1"))))
    with TestClient(app) as c:
        app.state.index_state = state
        app.state.retriever = ChromaRetriever(s, state=state)
        app.state.cache = cache
        return c.get("/readyz")


def test_readyz_redis_ok(monkeypatch) -> None:
    fake = FakeRedis()
    r = readyz(monkeypatch, SemanticCache(fake, 0.92, 60))
    assert r.status_code == 200 and r.json()["checks"]["redis"] == "ok"
    assert "idx:cache:idx-1" in fake.indexes                     # the current cache index exists


def test_readyz_redis_down_is_503_naming_redis(monkeypatch) -> None:
    fake = FakeRedis()
    fake.error = redis.ConnectionError("refused")
    r = readyz(monkeypatch, SemanticCache(fake, 0.92, 60))
    body = r.json()
    assert r.status_code == 503 and body["failed"] == ["redis"]
    assert body["checks"]["redis"] == "failed" and body["checks"]["chroma"] == "ok"
    assert body["checks"]["embed_dimension"] == "not_checked"


def test_readyz_chroma_failure_wins_over_redis(monkeypatch) -> None:
    fake = FakeRedis()
    fake.error = redis.ConnectionError("refused")
    r = readyz(monkeypatch, SemanticCache(fake, 0.92, 60), FakeClient(None))
    assert r.json()["failed"] == ["collection"] and fake.cmds == []   # Redis not even asked


def test_readyz_without_a_cache_says_skipped(monkeypatch) -> None:
    r = readyz(monkeypatch, None)
    assert r.status_code == 200 and r.json()["checks"]["redis"] == "skipped"


def test_healthz_never_touches_redis(monkeypatch) -> None:
    monkeypatch.setenv("RETRIEVER", "stub")
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    from app.main import app

    fake = FakeRedis()
    with TestClient(app) as c:
        app.state.cache = SemanticCache(fake, 0.92, 60)
        assert c.get("/healthz").status_code == 200
    assert fake.cmds == []
