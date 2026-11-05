"""IndexState: refresh, swap, pin, dimension (phase 8 AC-3, AC-4)."""

from __future__ import annotations

import logging

import pytest
from fakes import FakeClient, FakeCollection, meta, rows

from app.config import Settings
from app.services.index_state import IndexState, IndexUnavailable

S = Settings(embed_model="hashing-bow-768", index_refresh_seconds=10, collection="rahbar")


def _state(col: FakeCollection | None, now: list[float] | None = None) -> tuple[IndexState, FakeClient]:
    client = FakeClient(col)
    clock = now or [0.0]
    return IndexState(S, client=client, clock=lambda: clock[0]), client


def test_snapshot_fields_and_versions() -> None:
    st, _ = _state(FakeCollection(rows(), meta()))
    snap = st.get()
    assert (snap.index_id, snap.embed_model, snap.dimension, snap.chunk_count) == ("idx-1", "hashing-bow-768", 768, 2)
    assert snap.doc_versions == ["2023-08", "2026-06"] and st.problem() is None


def test_refreshes_only_after_interval_or_when_forced() -> None:
    now = [0.0]
    st, client = _state(FakeCollection(rows(), meta()), now)
    st.get()
    st.get()
    assert client.gets == 1
    now[0] = 11.0
    st.get()
    assert client.gets == 2
    st.get(force=True)
    assert client.gets == 3


def test_swap_is_picked_up_after_refresh() -> None:
    now = [0.0]
    st, client = _state(FakeCollection(rows(), meta("idx-1")), now)
    assert st.get().index_id == "idx-1"
    client.col = FakeCollection(rows(), meta("idx-2"))   # the indexer swapped the collection
    now[0] = 11.0
    assert st.get().index_id == "idx-2"


def test_pin_conflict_is_logged_once_with_both_models(caplog: pytest.LogCaptureFixture) -> None:
    st, _ = _state(FakeCollection(rows(), meta(model="dummy-768")))
    with caplog.at_level(logging.ERROR, logger="rahbar.index_state"):
        snap = st.get()
        st.get(force=True)
    recs = [r for r in caplog.records if r.getMessage() == "embedding pin conflict"]
    assert len(recs) == 1
    r = recs[0].__dict__
    assert (r["collection_embed_model"], r["api_embed_model"], r["collection"]) == ("dummy-768", "hashing-bow-768", "rahbar")
    assert st.problem() == "embed_pin"
    with pytest.raises(IndexUnavailable) as e:
        st.require_pin(snap)
    assert e.value.reason == "embed_pin"


def test_dimension_mismatch_sets_problem() -> None:
    st, _ = _state(FakeCollection(rows(), meta(dim=768)))
    snap = st.get()
    st.check_dimension(snap, 768)
    st2, _ = _state(FakeCollection(rows(), meta(dim=768)))
    snap2 = st2.get()
    with pytest.raises(IndexUnavailable) as e:
        st2.check_dimension(snap2, 384)
    assert e.value.reason == "dimension" and st2.problem() == "dimension"
    st2.get(force=True)
    assert st2.problem() == "dimension"   # stays until the index changes


def test_missing_and_empty_collection() -> None:
    st, _ = _state(None)
    with pytest.raises(IndexUnavailable) as e:
        st.get()
    assert e.value.reason == "collection"
    st, _ = _state(FakeCollection([], meta()))
    with pytest.raises(IndexUnavailable) as e:
        st.get()
    assert e.value.reason == "collection"


def test_chroma_down_without_snapshot_raises_with_one_keeps_serving() -> None:
    now = [0.0]
    st, client = _state(FakeCollection(rows(), meta()), now)
    client.error = ConnectionError("down")
    with pytest.raises(IndexUnavailable) as e:
        st.get()
    assert e.value.reason == "chroma" and st.problem() == "chroma"
    client.error = None
    first = st.get()
    client.error = ConnectionError("down")
    now[0] = 11.0
    assert st.get() is first   # D-59: stale snapshot survives a blip
    assert st.problem() == "chroma"
