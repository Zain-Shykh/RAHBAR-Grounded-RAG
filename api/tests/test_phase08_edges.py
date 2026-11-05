"""Independent tester's edge cases for phase 8 (scope, index state, retriever). No network."""

from __future__ import annotations

import json
import logging
import threading

import pytest
from fakes import FakeClient, FakeCollection, meta, row, rows

from app.config import Settings
from app.retrieval.chroma import ChromaRetriever
from app.services.index_state import IndexState, IndexUnavailable
from app.services.scope import scope

S = Settings(embed_model="hashing-bow-768", index_refresh_seconds=10, collection="rahbar")
V = ["2023-08", "2023-24", "2026-06"]


# ---- scope ----

@pytest.mark.parametrize("q", ["in (2023)?", "in 2023.", "in 2023, please", '"2023" rules', "2023/24 rules"])
def test_scope_year_survives_punctuation(q: str) -> None:
    assert scope(q, V).key == "2023-08+2023-24"


@pytest.mark.parametrize("q", ["FY2023 rules", "in 20233", "code 12023", "2023abc"])
def test_scope_year_glued_to_word_chars_is_not_a_year(q: str) -> None:
    assert scope(q, V).key == "current"


def test_scope_range_token_selects_only_that_version() -> None:
    assert scope("rules for 2023-24", V).key == "2023-24"


def test_scope_two_years_union_sorted() -> None:
    s = scope("compare 2026 and 2023-08", V)
    assert s.key == "2023-08+2026-06"
    assert s.where == {"doc_version": {"$in": ["2023-08", "2026-06"]}}


def test_scope_empty_question_and_empty_versions() -> None:
    assert scope("", V).key == "current"
    assert scope("rules in 2023", []).key == "current"
    assert scope("the old rules in 2023", []).key == "all"


def test_scope_older_phrase_is_case_insensitive_and_word_bounded() -> None:
    assert scope("What did the OLD handbook say?", V).key == "all"
    assert scope("USED  TO be different", V).key == "all"
    assert scope("Is the bold font mandatory? beforehand? golden", V).key == "current"


def test_scope_tag_is_stable_12_hex_and_differs_by_key() -> None:
    a, b = scope("x", V), scope("x in 2023", V)
    assert a.tag == scope("y", V).tag and len(a.tag) == 12 and int(a.tag, 16) >= 0
    assert a.tag != b.tag != scope("old x", V).tag


def test_scope_accepts_generator_and_duplicates() -> None:
    assert scope("in 2023", (v for v in V + V)).key == "2023-08+2023-24"


# ---- index state ----

def test_index_state_get_from_many_threads_fetches_once() -> None:
    client = FakeClient(FakeCollection(rows(), meta()))
    st = IndexState(S, client=client, clock=lambda: 0.0)
    snaps, errs = [], []
    barrier = threading.Barrier(16)

    def work() -> None:
        try:
            barrier.wait()
            snaps.append(st.get())
        except Exception as exc:   # pragma: no cover - failure path
            errs.append(exc)

    ts = [threading.Thread(target=work) for _ in range(16)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errs and len(snaps) == 16 and client.gets == 1
    assert len({s.index_id for s in snaps}) == 1


def test_index_state_concurrent_forced_refresh_never_returns_none() -> None:
    client = FakeClient(FakeCollection(rows(), meta()))
    st = IndexState(S, client=client, clock=lambda: 0.0)
    st.get()
    out, errs = [], []

    def work() -> None:
        try:
            for _ in range(50):
                out.append(st.get(force=True))
        except Exception as exc:   # pragma: no cover
            errs.append(exc)

    ts = [threading.Thread(target=work) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errs and len(out) == 400 and all(s.chunk_count == 2 for s in out)


def test_pin_conflict_logs_again_for_new_index_id_and_clears_after_fix(caplog: pytest.LogCaptureFixture) -> None:
    client = FakeClient(FakeCollection(rows(), meta("idx-1", model="other-model")))
    st = IndexState(S, client=client, clock=lambda: 0.0)
    with caplog.at_level(logging.ERROR, logger="rahbar.index_state"):
        st.get()
        st.get(force=True)
        assert len([r for r in caplog.records if r.msg == "embedding pin conflict"]) == 1
        client.col = FakeCollection(rows(), meta("idx-2", model="other-model"))
        st.get(force=True)
        assert len([r for r in caplog.records if r.msg == "embedding pin conflict"]) == 2
    assert st.problem() == "embed_pin"
    client.col = FakeCollection(rows(), meta("idx-3"))   # the indexer re-ran with the pinned model
    st.get(force=True)
    assert st.problem() is None


def test_dimension_problem_clears_when_index_is_swapped_to_good_one() -> None:
    client = FakeClient(FakeCollection(rows(), meta("idx-1", dim=384)))
    r = ChromaRetriever(S, state=IndexState(S, client=client, clock=lambda: 0.0))
    with pytest.raises(IndexUnavailable):
        r.retrieve("q", 2)
    r.state.get(force=True)
    assert r.state.problem() == "dimension"   # sticky for the same index_id
    client.col = FakeCollection(rows(), meta("idx-2"))
    r.state.get(force=True)
    assert r.state.problem() is None and len(r.retrieve("q", 2)) == 2


@pytest.mark.parametrize("bad", ["not json", "{}", '[{"source": "a.pdf"}]', "null"])
def test_malformed_doc_versions_metadata_is_index_unavailable_not_a_crash(bad: str) -> None:
    m = meta()
    m["doc_versions"] = bad
    st = IndexState(S, client=FakeClient(FakeCollection(rows(), m)), clock=lambda: 0.0)
    with pytest.raises(IndexUnavailable):
        st.get()


def test_collection_without_metadata_is_not_a_crash() -> None:
    st = IndexState(S, client=FakeClient(FakeCollection(rows(), {})), clock=lambda: 0.0)
    try:
        st.get()
    except IndexUnavailable:
        pass
    assert st.problem() in ("embed_pin", "collection", "chroma", "dimension")


def test_force_refresh_to_missing_collection_raises_collection() -> None:
    client = FakeClient(FakeCollection(rows(), meta()))
    st = IndexState(S, client=client, clock=lambda: 0.0)
    st.get()
    client.col = None
    with pytest.raises(IndexUnavailable) as e:
        st.get(force=True)
    assert e.value.reason == "collection" and st.problem() == "collection"


# ---- retriever ----

def _r(rows_: list[dict], m: dict | None = None) -> tuple[ChromaRetriever, FakeCollection]:
    col = FakeCollection(rows_, m or meta())
    return ChromaRetriever(S, state=IndexState(S, client=FakeClient(col), clock=lambda: 0.0)), col


def test_k_larger_than_collection_returns_all_rows() -> None:
    r, col = _r(rows())
    assert len(r.retrieve("q", 1000)) == 2 and col.queries[0]["n_results"] == 1000


def test_no_hits_returns_empty_list() -> None:
    r, _ = _r([])
    with pytest.raises(IndexUnavailable):   # an empty collection is "collection" unavailable, not []
        r.retrieve("q", 3)
    r2, _ = _r(rows())
    assert r2.retrieve("q", 3, where={"doc_version": {"$in": ["1999"]}}) == []


def test_empty_where_is_not_sent_to_chroma() -> None:
    r, col = _r(rows())
    r.retrieve("q", 2, where={})
    r.retrieve("q", 2, where=None)
    assert all("where" not in q for q in col.queries)


@pytest.mark.parametrize("page,expected", [(0, None), (-3, None), (None, None), ("7", None), (12, 12)])
def test_page_values(page: object, expected: int | None) -> None:
    data = [row("c1", "a.pdf", "1", "2026-06", False, 0.1)]
    data[0]["md"]["page"] = page
    r, _ = _r(data)
    assert r.retrieve("q", 1)[0].page == expected


def test_missing_page_key_maps_to_none() -> None:
    data = [row("c1", "a.pdf", "1", "2026-06", False, 0.1)]
    del data[0]["md"]["page"]
    r, _ = _r(data)
    assert r.retrieve("q", 1)[0].page is None


def test_score_is_one_minus_distance_including_out_of_range() -> None:
    data = [row("c1", "a.pdf", "1", "2026-06", False, 0.0), row("c2", "a.pdf", "2", "2026-06", False, 1.4)]
    r, _ = _r(data)
    out = r.retrieve("q", 2)
    assert out[0].score == pytest.approx(1.0) and out[1].score == pytest.approx(-0.4)


def test_chroma_down_at_query_time_with_stale_snapshot_is_index_unavailable() -> None:
    col = FakeCollection(rows(), meta())
    client = FakeClient(col)
    now = [0.0]
    r = ChromaRetriever(S, state=IndexState(S, client=client, clock=lambda: now[0]))
    r.retrieve("q", 2)
    client.error = ConnectionError("down")
    col.fail_next = ConnectionError("down")
    now[0] = 100.0   # refresh due, fails, previous snapshot served, query then fails honestly
    with pytest.raises(IndexUnavailable) as e:
        r.retrieve("q", 2)
    assert e.value.reason == "chroma"


def test_swap_to_missing_collection_during_query_raises_index_unavailable() -> None:
    col = FakeCollection(rows(), meta())
    client = FakeClient(col)
    r = ChromaRetriever(S, state=IndexState(S, client=client, clock=lambda: 0.0))
    r.retrieve("q", 2)
    from fakes import NotFoundError
    col.fail_next = NotFoundError("gone")
    client.col = None
    with pytest.raises(IndexUnavailable):
        r.retrieve("q", 2)


def test_retriever_never_calls_a_chroma_write_api() -> None:
    class Strict(FakeCollection):
        def __getattr__(self, name: str) -> object:
            raise AssertionError(f"unexpected collection attribute {name}")

    col = Strict(rows(), meta())
    r = ChromaRetriever(S, state=IndexState(S, client=FakeClient(col), clock=lambda: 0.0))
    r.retrieve("q", 2)   # only count/query/metadata may be touched


def test_metadata_json_roundtrip_helper_sanity() -> None:
    assert json.loads(meta()["doc_versions"])[0]["doc_version"] == "2026-06"
