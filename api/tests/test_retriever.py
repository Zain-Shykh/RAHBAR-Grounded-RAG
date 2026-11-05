"""ChromaRetriever with a fake collection and the offline embedder (phase 8 AC-1 logic, AC-3, AC-4)."""

from __future__ import annotations

import pytest
from fakes import FakeClient, FakeCollection, NotFoundError, meta, rows

from app.config import Settings
from app.retrieval.chroma import ChromaRetriever
from app.services.index_state import IndexState, IndexUnavailable
from app.services.scope import scope

S = Settings(embed_model="hashing-bow-768")


def _retriever(col: FakeCollection | None, settings: Settings = S) -> tuple[ChromaRetriever, FakeClient]:
    client = FakeClient(col)
    return ChromaRetriever(settings, state=IndexState(settings, client=client)), client


def test_maps_hits_to_passages_with_similarity_score() -> None:
    r, _ = _retriever(FakeCollection(rows(), meta()))
    out = r.retrieve("withdraw deadline", 5)
    assert [p.chunk_id for p in out] == ["c1", "c2"]
    assert out[0].score == pytest.approx(0.8) and out[0].source == "a.pdf" and out[0].page == 1


def test_query_uses_where_vector_and_includes() -> None:
    col = FakeCollection(rows(), meta())
    r, _ = _retriever(col)
    r.retrieve("q", 3, where={"superseded": False})
    q = col.queries[0]
    assert q["n_results"] == 3 and q["where"] == {"superseded": False} and len(q["query_embeddings"][0]) == 768
    assert q["include"] == ["documents", "metadatas", "distances"]


def test_scope_filters_versions() -> None:
    col = FakeCollection(rows(), meta())
    r, client = _retriever(col)
    versions = r.state.get().doc_versions
    assert [p.chunk_id for p in r.retrieve("rules in 2023", 5, where=scope("rules in 2023", versions).where)] == ["c2"]
    assert [p.chunk_id for p in r.retrieve("rules", 5, where=scope("rules", versions).where)] == ["c1"]
    assert len(r.retrieve("the old rules", 5, where=scope("the old rules", versions).where)) == 2


def test_supplied_vector_skips_embedding() -> None:
    col = FakeCollection(rows(), meta())
    r, _ = _retriever(col)

    class Boom:
        model = "hashing-bow-768"
        def embed_query(self, q: str) -> list[float]:
            raise AssertionError("must not embed")

    r.embedder = Boom()
    r.retrieve("q", 2, vector=[0.0] * 768)
    assert col.queries[0]["query_embeddings"] == [[0.0] * 768]


def test_swap_retry_re_resolves_once() -> None:
    old = FakeCollection(rows(), meta("idx-1"))
    r, client = _retriever(old)
    r.retrieve("q", 2)
    old.fail_next = NotFoundError("Collection does not exist")   # swapped away under us
    client.col = FakeCollection(rows(), meta("idx-2"))
    assert len(r.retrieve("q", 2)) == 2
    assert r.state.get().index_id == "idx-2"


def test_second_not_found_becomes_index_unavailable() -> None:
    col = FakeCollection(rows(), meta())
    r, _ = _retriever(col)
    r.retrieve("q", 2)
    col.fail_next = NotFoundError("gone")
    # the re-resolved collection is the same object; make it fail again on the retry
    orig = col.query
    calls = []

    def always(**kw):  # type: ignore[no-untyped-def]
        calls.append(1)
        raise NotFoundError("gone")

    col.query = always  # type: ignore[method-assign]
    with pytest.raises(IndexUnavailable) as e:
        r.retrieve("q", 2)
    assert e.value.reason == "chroma" and len(calls) == 2
    col.query = orig  # type: ignore[method-assign]


def test_other_chroma_error_is_index_unavailable() -> None:
    col = FakeCollection(rows(), meta())
    r, _ = _retriever(col)
    r.retrieve("q", 2)
    col.fail_next = ConnectionError("reset")
    with pytest.raises(IndexUnavailable) as e:
        r.retrieve("q", 2)
    assert e.value.reason == "chroma"


def test_pin_conflict_blocks_retrieval() -> None:
    col = FakeCollection(rows(), meta(model="dummy-768"))
    r, _ = _retriever(col)
    with pytest.raises(IndexUnavailable) as e:
        r.retrieve("q", 2)
    assert e.value.reason == "embed_pin" and col.queries == []


def test_dimension_mismatch_blocks_retrieval() -> None:
    col = FakeCollection(rows(), meta(dim=384))
    r, _ = _retriever(col)
    with pytest.raises(IndexUnavailable) as e:
        r.retrieve("q", 2)
    assert e.value.reason == "dimension" and col.queries == []


@pytest.mark.parametrize("break_row", [
    lambda d: d[0]["md"].pop("source"),
    lambda d: d[0]["md"].pop("section"),
    lambda d: d[0].update(md=None),
])
def test_malformed_row_is_index_unavailable(break_row) -> None:  # type: ignore[no-untyped-def]
    data = rows()
    break_row(data)
    r, _ = _retriever(FakeCollection(data, meta()))
    with pytest.raises(IndexUnavailable) as e:
        r.retrieve("q", 2)
    assert e.value.reason == "chroma"


def test_missing_page_maps_to_none() -> None:
    data = rows()
    data[0]["md"]["page"] = 0
    r, _ = _retriever(FakeCollection(data, meta()))
    assert r.retrieve("q", 1)[0].page is None


def test_app_starts_without_chroma_and_stub_has_no_state(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setenv("RETRIEVER", "stub")
    with TestClient(app):
        assert app.state.index_state is None
    monkeypatch.setenv("RETRIEVER", "chroma")
    monkeypatch.setenv("EMBED_MODEL", "hashing-bow-768")
    monkeypatch.setenv("CHROMA_HOST", "127.0.0.1")
    monkeypatch.setenv("CHROMA_PORT", "1")   # nothing listens: start-up must log and carry on
    with TestClient(app) as c:
        assert c.get("/healthz").status_code == 200
        assert app.state.index_state.problem() == "chroma"


def test_unknown_embed_model_does_not_crash_construction() -> None:
    s = Settings(embed_model="other")
    r, _ = _retriever(FakeCollection(rows(), meta(model="other")), s)   # collection agrees, embedder unknown
    with pytest.raises(IndexUnavailable) as e:
        r.retrieve("q", 2)
    assert e.value.reason == "embed_pin" and "unknown EMBED_MODEL" in str(e.value)
    r2, _ = _retriever(FakeCollection(rows(), meta(model="hashing-bow-768")), s)   # the real mismatch
    with pytest.raises(IndexUnavailable) as e2:
        r2.retrieve("q", 2)
    assert e2.value.reason == "embed_pin" and r2.state.problem() == "embed_pin"
