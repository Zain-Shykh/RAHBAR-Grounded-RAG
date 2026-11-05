"""/metrics exposes every name of architecture 4.14 (AC-5)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

NAMES = [
    "rahbar_requests_total", "rahbar_request_duration_seconds", "rahbar_request_seconds",
    "rahbar_embed_seconds", "rahbar_retrieval_seconds", "rahbar_generation_seconds",
    "rahbar_cache_lookups_total", "rahbar_cache_hit_ratio", "rahbar_abstentions_total",
    "rahbar_fallbacks_total", "rahbar_tokens", "rahbar_top_score", "rahbar_index_info",
]


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("RETRIEVER", "stub")
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_every_metric_name_is_exposed(client: TestClient) -> None:
    text = client.get("/metrics").text
    missing = [n for n in NAMES if f"# TYPE {n} " not in text]
    assert not missing


def test_request_latency_has_both_names(client: TestClient) -> None:
    client.get("/healthz")
    text = client.get("/metrics").text
    assert 'rahbar_request_seconds_count{path="/healthz"}' in text
    assert 'rahbar_request_duration_seconds_count{path="/healthz"}' in text


def test_index_info_keeps_one_live_label_set() -> None:
    from app.routes import metrics

    metrics.set_index_info("m", "idx-a", 10)
    metrics.set_index_info("m", "idx-b", 11)
    metrics.set_index_info("m", "idx-b", 11)
    from prometheus_client import generate_latest

    lines = [x for x in generate_latest().decode().splitlines() if x.startswith("rahbar_index_info{")]
    assert len(lines) == 1 and 'index_id="idx-b"' in lines[0] and lines[0].endswith(" 1.0")
