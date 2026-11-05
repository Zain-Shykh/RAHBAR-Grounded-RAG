"""Tester round 1, phase 10: edges the unit tests above do not pin. No network, no model."""

from __future__ import annotations

import logging
import time

import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from app.config import Settings
from app.providers.llm.base import InvalidModelOutput, ProviderError
from app.retrieval.chroma import ChromaRetriever
from app.schemas import Answer, Citation
from app.services.answer import answer_question
from app.services.index_state import IndexState
from app.services.validate import validate
from tests.fakes import FakeClient, FakeCollection, meta, rows
from tests.test_answer import FakeRetriever, P, S, Scripted, ans, counter, run


def test_probe3_huge_duplicate_citation_list_is_deduplicated_and_fast() -> None:
    c = Citation(source="d1.pdf", section="1.1", page=1)
    a = Answer(reasoning="r", answer="x", citations=[c] * 5000, answered_from_context=True, confidence="high")
    t = time.perf_counter()
    out = validate(a, [P(1)])
    assert len(out.citations) == 1 and time.perf_counter() - t < 1.0


def test_probe3_huge_citation_list_with_one_fabricated_entry_is_rejected() -> None:
    cs = [Citation(source="d1.pdf", section="1.1", page=1)] * 3000 + [Citation(source="x.pdf", section="9")]
    a = Answer(reasoning="r", answer="x", citations=cs, answered_from_context=True, confidence="high")
    with pytest.raises(InvalidModelOutput, match="bad_citation"):
        validate(a, [P(1)])


def test_probe3_retry_hint_names_the_reason_and_the_evidence_rule() -> None:
    bad = ans(1).model_copy(update={"citations": [Citation(source="nope.pdf", section="7")]})
    p = Scripted(bad, ans(1))
    assert run([P(1)], p).outcome == "answered"
    hint = p.calls[1]["hint"]
    assert p.calls[0]["hint"] is None
    assert "bad_citation: nope.pdf / 7" in hint and "evidence" in hint


def test_probe3_transient_then_invalid_output_is_invalid_output_fallback() -> None:
    p = Scripted(ProviderError("t", transient=True), InvalidModelOutput("not_json"))
    before = counter("rahbar_fallbacks_total", reason="invalid_output")
    r = run([P(1)], p)
    assert r.outcome == "fallback" and len(p.calls) == 2
    assert counter("rahbar_fallbacks_total", reason="invalid_output") == before + 1


def test_probe3_invalid_then_transient_error_is_provider_error_fallback() -> None:
    p = Scripted(InvalidModelOutput("schema"), ProviderError("t", transient=True))
    before = counter("rahbar_fallbacks_total", reason="provider_error")
    assert run([P(1)], p).outcome == "fallback"
    assert counter("rahbar_fallbacks_total", reason="provider_error") == before + 1


def test_probe3_tokens_are_summed_over_attempts_in_the_log(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="rahbar.answer")
    run([P(1)], Scripted(ans(1, cite=False), ans(1)))
    rec = next(r for r in caplog.records if r.getMessage() == "answered")
    assert (rec.tokens_in, rec.tokens_out) == (200, 40)


def test_probe3_model_abstention_never_carries_citations_or_reasoning() -> None:
    r = run([P(1)], Scripted(ans(1, yes=False)))
    assert r.outcome == "abstained" and r.response.citations == []
    assert "reasoning" not in r.response.model_dump()


def test_probe3_metric_label_values_stay_in_the_fixed_sets() -> None:
    run([P(1, 0.1)], Scripted())
    run([P(1)], Scripted(ans(1, yes=False)))
    run([P(1)], Scripted(InvalidModelOutput("x"), InvalidModelOutput("y")))
    seen = {
        name: {s.labels["reason"] for f in REGISTRY.collect() for s in f.samples if s.name == name}
        for name in ("rahbar_abstentions_total", "rahbar_fallbacks_total")
    }
    assert seen["rahbar_abstentions_total"] <= {"below_floor", "model"}
    assert seen["rahbar_fallbacks_total"] <= {"provider_error", "invalid_output", "bad_citation"}


@pytest.fixture()
def app_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("RETRIEVER", "stub")
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c, app


def test_probe3_chroma_failing_mid_request_is_503_not_500(app_client) -> None:
    c, app = app_client
    s = Settings(embed_model="hashing-bow-768", index_refresh_seconds=0, relevance_floor=0.0)
    fake = FakeClient(FakeCollection(rows(), meta()))
    state = IndexState(s, client=fake)
    app.state.retriever = ChromaRetriever(s, state=state)
    app.state.provider = Scripted()
    fake.col.fail_next = RuntimeError("connection reset")
    r = c.post("/api/ask", json={"question": "What is the attendance rule?"})
    assert r.status_code == 503 and r.json() == {"detail": "index unavailable"}
    assert r.headers["X-Request-ID"] and "X-Outcome" not in r.headers


def test_probe3_request_id_header_on_validation_error_and_is_echoed(app_client) -> None:
    c, _ = app_client
    r = c.post("/api/ask", json={"question": "x"}, headers={"X-Request-ID": "abc-123"})
    assert r.status_code == 422 and r.headers["X-Request-ID"] == "abc-123"


def test_probe3_provider_exception_with_odd_type_is_a_fallback_through_the_route(app_client) -> None:
    c, app = app_client
    app.state.retriever = FakeRetriever([P(1)])
    app.state.provider = Scripted(KeyError("boom"))
    r = c.post("/api/ask", json={"question": "What is the attendance rule?"})
    assert r.status_code == 200 and r.headers["X-Outcome"] == "fallback"
    assert r.json()["citations"] == [] and r.json()["answered_from_context"] is False


def test_probe3_answer_log_line_has_no_question_text(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="rahbar.answer")
    answer_question("What is the SECRETWORD attendance rule?", FakeRetriever([P(1)]),
                    Scripted(ans(1)), S)
    rec = next(r for r in caplog.records if r.getMessage() == "answered")
    assert "SECRETWORD" not in repr(rec.__dict__)
