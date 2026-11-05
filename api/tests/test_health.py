"""/healthz touches nothing; /readyz is honest (AC-3, AC-4). Fake Chroma, no network."""

from __future__ import annotations

import json
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.retrieval.chroma import ChromaRetriever
from app.services.index_state import IndexState
from tests.fakes import FakeClient, FakeCollection, meta, rows


def make_client(monkeypatch: pytest.MonkeyPatch, fake: FakeClient, **settings: Any):
    monkeypatch.setenv("RETRIEVER", "stub")
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    from app.main import app

    s = Settings(embed_model="hashing-bow-768", index_refresh_seconds=0, **settings)
    return app, s, IndexState(s, client=fake)


def ready(monkeypatch, fake: FakeClient, **settings):
    app, s, state = make_client(monkeypatch, fake, **settings)
    with TestClient(app) as c:
        app.state.index_state = state
        app.state.retriever = ChromaRetriever(s, state=state)
        return c.get("/readyz")


def col(**kw: Any) -> FakeClient:
    return FakeClient(FakeCollection(rows(), meta(**kw)))


def test_ready_with_a_good_index(monkeypatch) -> None:
    r = ready(monkeypatch, col())
    assert r.status_code == 200 and r.json()["status"] == "ready"
    assert r.json()["checks"]["chroma"] == "ok" and r.json()["checks"]["redis"] == "skipped"


def test_embed_pin_mismatch_is_503_and_logged(monkeypatch, capsys) -> None:
    r = ready(monkeypatch, col(model="nomic-embed-text"))
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "not_ready" and body["failed"] == ["embed_pin"]
    assert body["checks"]["embed_pin"] == "failed"
    lines = [json.loads(x) for x in capsys.readouterr().out.splitlines() if x.startswith("{")]
    (rec,) = [x for x in lines if x["msg"] == "embedding pin conflict"]   # the JSON line on stdout (5.3)
    assert rec["collection_embed_model"] == "nomic-embed-text"
    assert rec["api_embed_model"] == "hashing-bow-768" and rec["collection"] == "rahbar"


def test_missing_collection_is_503_collection(monkeypatch) -> None:
    r = ready(monkeypatch, FakeClient(None))
    assert r.status_code == 503 and r.json()["failed"] == ["collection"]


def test_empty_collection_is_503_collection(monkeypatch) -> None:
    r = ready(monkeypatch, FakeClient(FakeCollection([], meta())))
    assert r.status_code == 503 and r.json()["failed"] == ["collection"]


def test_chroma_down_is_503_chroma(monkeypatch) -> None:
    fake = col()
    fake.error = ConnectionError("refused")
    r = ready(monkeypatch, fake)
    assert r.status_code == 503 and r.json()["failed"] == ["chroma"]


def test_chroma_down_after_a_good_snapshot_is_still_503(monkeypatch) -> None:
    fake = col()
    app, s, state = make_client(monkeypatch, fake)
    with TestClient(app) as c:
        app.state.index_state = state
        assert c.get("/readyz").status_code == 200
        fake.error = ConnectionError("refused")
        r = c.get("/readyz")
    assert r.status_code == 503 and r.json()["failed"] == ["chroma"]


def test_hung_chroma_is_503_within_the_timeout(monkeypatch) -> None:
    class Hang(FakeClient):
        def get_collection(self, name: str):
            time.sleep(5)

    import app.routes.health as health

    monkeypatch.setattr(health, "CHECK_TIMEOUT", 0.2)
    t = time.perf_counter()
    r = ready(monkeypatch, Hang(None))
    assert r.status_code == 503 and r.json()["failed"] == ["chroma"]
    assert time.perf_counter() - t < 2


def test_dimension_conflict_flips_readiness(monkeypatch) -> None:
    fake = col(dim=768)
    app, s, state = make_client(monkeypatch, fake)
    with TestClient(app) as c:
        app.state.index_state = state
        snap = state.get()
        with pytest.raises(Exception):
            state.check_dimension(snap, 384)
        r = c.get("/readyz")
    assert r.status_code == 503 and r.json()["failed"] == ["embed_dimension"]


def test_stub_mode_is_ready(monkeypatch) -> None:
    monkeypatch.setenv("RETRIEVER", "stub")
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    from app.main import app

    with TestClient(app) as c:
        assert c.get("/readyz").status_code == 200


def test_readyz_publishes_index_info(monkeypatch) -> None:
    ready(monkeypatch, col(index_id="idx-live"))
    from prometheus_client import generate_latest

    assert 'rahbar_index_info{chunks="2",embed_model="hashing-bow-768",index_id="idx-live"} 1.0' in \
        generate_latest().decode()


def test_healthz_body_and_version(monkeypatch) -> None:
    monkeypatch.setenv("RETRIEVER", "stub")
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.setenv("APP_VERSION", "9.9.9")
    from app.main import app

    with TestClient(app) as c:
        assert c.get("/healthz").json() == {"status": "alive", "version": "9.9.9"}


def test_healthz_touches_nothing(monkeypatch) -> None:
    """Every dependency raises on any use: /healthz is still 200."""
    class Boom:
        def __getattr__(self, name: str):
            raise AssertionError(f"/healthz touched {name}")

    monkeypatch.setenv("RETRIEVER", "stub")
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    from app.main import app

    with TestClient(app) as c:
        app.state.index_state = Boom()
        app.state.retriever = Boom()
        app.state.provider = Boom()
        r = c.get("/healthz")
    assert r.status_code == 200 and r.json()["status"] == "alive"
