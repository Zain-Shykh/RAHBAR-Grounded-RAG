"""Stage-and-swap store (phase 7 spec AC-3, AC-4, AC-9)."""

from __future__ import annotations

import json
import re

import pytest
from fakechroma import FakeClient
from pipeline.config import IndexerSettings
from pipeline.models import Chunk
from pipeline.store import StoreError, store, validate, wait_for_chroma


def _settings(model: str = "hashing-bow-768") -> IndexerSettings:
    return IndexerSettings(embed_model=model, chroma_host="h", chroma_port=1, collection="rahbar",
                           corpus_dir="d", chunk_size=400, chunk_overlap=50, ollama_url="http://o")


def _chunks(n: int, version: str = "2026-06", superseded: bool = False) -> list[Chunk]:
    return [Chunk(f"doc-p001-c{i:03d}", f"text {i}", "doc.pdf", f"{i}. Head", 1, version, superseded)
            for i in range(n)]


def _vecs(n: int) -> list[list[float]]:
    return [[1.0] + [0.0] * 767 for _ in range(n)]


def test_first_build_writes_all_metadata() -> None:
    c = FakeClient()
    assert store(_chunks(3), _vecs(3), _settings(), c) == 3
    assert list(c.cols) == ["rahbar"]  # no rahbar_next left
    col = c.cols["rahbar"]
    m = col.metadata
    assert set(m) == {"hnsw:space", "embed_model", "dimension", "index_id", "built_at", "chunk_count",
                      "chunk_size", "chunk_overlap", "doc_versions"}
    assert m["hnsw:space"] == "cosine" and m["embed_model"] == "hashing-bow-768" and m["dimension"] == 768
    assert m["chunk_count"] == 3 and (m["chunk_size"], m["chunk_overlap"]) == (400, 50)
    assert re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{6}", m["index_id"])
    assert json.loads(m["doc_versions"]) == [{"source": "doc.pdf", "doc_version": "2026-06", "superseded": False}]
    assert col.docs == ["text 0", "text 1", "text 2"]
    assert set(col.metas[0]) == {"source", "section", "page", "doc_version", "superseded"}


def test_second_run_replaces_and_changes_index_id() -> None:
    c = FakeClient()
    store(_chunks(3), _vecs(3), _settings(), c)
    first = c.cols["rahbar"].metadata["index_id"]
    store(_chunks(3), _vecs(3), _settings(), c)
    assert list(c.cols) == ["rahbar"] and c.cols["rahbar"].metadata["index_id"] != first
    assert c.cols["rahbar"].count() == 3


def test_adds_in_batches_of_at_most_500() -> None:
    c = FakeClient()
    store(_chunks(1201), _vecs(1201), _settings(), c)
    assert c.cols["rahbar"].add_sizes == [500, 500, 201]


def test_failure_while_adding_keeps_live_collection() -> None:
    c = FakeClient()
    store(_chunks(2), _vecs(2), _settings(), c)
    old = c.cols["rahbar"]
    old_id = old.metadata["index_id"]
    c.fail_add_on_call = 2
    with pytest.raises(RuntimeError):
        store(_chunks(1100), _vecs(1100), _settings(), c)
    assert list(c.cols) == ["rahbar"] and c.cols["rahbar"] is old
    assert old.metadata["index_id"] == old_id and old.count() == 2


def test_count_mismatch_deletes_staging_keeps_live() -> None:
    c = FakeClient()
    store(_chunks(2), _vecs(2), _settings(), c)
    old_id = c.cols["rahbar"].metadata["index_id"]
    c.lose_records = 1
    with pytest.raises(StoreError, match="expected"):
        store(_chunks(4), _vecs(4), _settings(), c)
    assert list(c.cols) == ["rahbar"] and c.cols["rahbar"].metadata["index_id"] == old_id


def test_leftover_staging_collection_is_removed_first() -> None:
    c = FakeClient()
    c.create_collection("rahbar_next", {})
    store(_chunks(2), _vecs(2), _settings(), c)
    assert list(c.cols) == ["rahbar"] and c.cols["rahbar"].count() == 2


def test_live_deleted_only_after_staging_verified() -> None:
    c = FakeClient()
    store(_chunks(1), _vecs(1), _settings(), c)
    c.calls.clear()
    store(_chunks(2), _vecs(2), _settings(), c)
    assert c.calls == ["delete rahbar_next", "create rahbar_next", "delete rahbar"]


@pytest.mark.parametrize("mutate,msg", [
    (lambda ch, v: (ch, v[:-1]), "vectors"),
    (lambda ch, v: ([], []), "no chunks"),
    (lambda ch, v: ([ch[0], ch[0]], v[:2]), "duplicate"),
    (lambda ch, v: ([Chunk("x", "  ", "d", "s", 1, "v", False)], v[:1]), "empty"),
    (lambda ch, v: (ch, [v[0][:10]] * 3), "length"),
])
def test_validation_fails_before_any_write(mutate, msg: str) -> None:  # type: ignore[no-untyped-def]
    c = FakeClient()
    ch, v = mutate(_chunks(3), _vecs(3))
    with pytest.raises(StoreError, match=msg):
        store(ch, v, _settings(), c)
    assert c.calls == [] and c.cols == {}


def test_validate_rejects_unknown_model() -> None:
    with pytest.raises(ValueError):
        validate(_chunks(1), _vecs(1), "other-model")


def test_doc_versions_lists_each_document_once() -> None:
    c = FakeClient()
    chunks = _chunks(2) + [Chunk("o-p001-c000", "old", "old.pdf", "h", 1, "2023-08", True)]
    store(chunks, _vecs(3), _settings(), c)
    dv = json.loads(c.cols["rahbar"].metadata["doc_versions"])
    assert dv == [{"source": "doc.pdf", "doc_version": "2026-06", "superseded": False},
                  {"source": "old.pdf", "doc_version": "2023-08", "superseded": True}]


def test_wait_for_chroma_retries_then_times_out() -> None:
    class Down:
        n = 0

        def heartbeat(self) -> int:
            self.n += 1
            raise ConnectionError("no")

    d, sleeps = Down(), []
    with pytest.raises(TimeoutError):
        wait_for_chroma(_settings(), 0.0, client=d, sleep=sleeps.append)
    assert d.n == 1

    class Late:
        n = 0

        def heartbeat(self) -> int:
            self.n += 1
            if self.n < 3:
                raise ConnectionError("no")
            return 1

    late = Late()
    wait_for_chroma(_settings(), 60.0, client=late, sleep=lambda s: None)
    assert late.n == 3
