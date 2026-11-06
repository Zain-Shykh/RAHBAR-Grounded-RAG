"""Tester-added edge cases for phase 7 (embed, store, run). No network, model or cluster."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fakechroma import FakeClient, FakeCollection
from pipeline import run as runmod
from pipeline import store as storemod
from pipeline.config import IndexerSettings
from pipeline.embed import embed
from pipeline.embedding.hashing import embed_hashing
from pipeline.embedding.ollama import EmbedError, embed_ollama
from pipeline.models import Chunk
from pipeline.store import StoreError, store


def _settings(corpus: str = "d", model: str = "hashing-bow-768") -> IndexerSettings:
    return IndexerSettings(embed_model=model, chroma_host="h", chroma_port=1, collection="rahbar",
                           corpus_dir=corpus, chunk_size=50, chunk_overlap=5, ollama_url="http://o",
                           chroma_wait_seconds=0.0)


def _chunks(n: int, text: str = "text") -> list[Chunk]:
    return [Chunk(f"d-p001-c{i:03d}", f"{text} {i}", "d.pdf", "1. H", 1, "2026-06", False) for i in range(n)]


def _vecs(n: int) -> list[list[float]]:
    return [[1.0] + [0.0] * 767 for _ in range(n)]


# ---- store -----------------------------------------------------------------------------------

def test_non_ascii_text_and_section_are_stored_verbatim() -> None:
    c = FakeClient()
    ch = [Chunk("d-p001-c001", "Café naïve 日本語 العربية 😀", "d.pdf",
                "§ 1. Résumé", 1, "2026-06", False)]
    store(ch, _vecs(1), _settings(), c)
    col = c.cols["rahbar"]
    assert col.docs == [ch[0].text] and col.metas[0]["section"] == "§ 1. Résumé"
    json.loads(col.metadata["doc_versions"])  # still valid JSON


def test_rename_failure_after_live_deleted_leaves_staging_and_next_run_recovers(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Crash between delete and rename: staging stays; the next run removes it and succeeds."""
    c = FakeClient()
    store(_chunks(2), _vecs(2), _settings(), c)
    real = FakeCollection.modify

    def boom(self: object, name: str) -> None:
        raise RuntimeError("crash before rename")

    monkeypatch.setattr(FakeCollection, "modify", boom)
    with pytest.raises(RuntimeError):
        store(_chunks(3), _vecs(3), _settings(), c)
    assert "rahbar" not in c.cols and "rahbar_next" in c.cols  # accepted gap (AD-20)
    monkeypatch.setattr(FakeCollection, "modify", real)
    store(_chunks(3), _vecs(3), _settings(), c)
    assert list(c.cols) == ["rahbar"] and c.cols["rahbar"].count() == 3


def test_keyboard_interrupt_while_adding_cleans_staging_and_keeps_live(monkeypatch: pytest.MonkeyPatch) -> None:
    c = FakeClient()
    store(_chunks(2), _vecs(2), _settings(), c)
    live = c.cols["rahbar"]

    def interrupt(self: object, *a: object, **k: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(FakeCollection, "add", interrupt)
    with pytest.raises(KeyboardInterrupt):
        store(_chunks(3), _vecs(3), _settings(), c)
    assert list(c.cols) == ["rahbar"] and c.cols["rahbar"] is live


def test_batch_boundaries_500_501_1000() -> None:
    for n, sizes in ((500, [500]), (501, [500, 1]), (1000, [500, 500])):
        c = FakeClient()
        store(_chunks(n), _vecs(n), _settings(), c)
        assert c.cols["rahbar"].add_sizes == sizes


def test_vectors_with_wrong_dimension_for_model_are_rejected_before_write() -> None:
    c = FakeClient()
    with pytest.raises(StoreError, match="768"):
        store(_chunks(2), [[1.0] * 384] * 2, _settings(), c)
    assert c.calls == []


def test_chunk_metadata_types_survive_into_records() -> None:
    c = FakeClient()
    ch = [Chunk("d-p007-c001", "t", "old.pdf", "s", 7, "2023-08", True)]
    store(ch, _vecs(1), _settings(), c)
    m = c.cols["rahbar"].metas[0]
    assert m == {"source": "old.pdf", "section": "s", "page": 7, "doc_version": "2023-08", "superseded": True}
    assert isinstance(m["page"], int) and m["superseded"] is True


def test_embed_model_in_metadata_is_the_configured_pin() -> None:
    c = FakeClient()
    store(_chunks(1), _vecs(1), _settings(model="nomic-embed-text"), c)
    assert c.cols["rahbar"].metadata["embed_model"] == "nomic-embed-text"


# ---- ollama / embed --------------------------------------------------------------------------

def test_empty_text_list_makes_no_request() -> None:
    def never(r: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    assert embed_ollama([], "nomic-embed-text", "http://o", 32, transport=httpx.MockTransport(never)) == []


def test_batch_boundaries_32_33_64() -> None:
    for n, expect in ((32, [32]), (33, [32, 1]), (64, [32, 32])):
        seen: list[int] = []

        def h(r: httpx.Request, seen: list[int] = seen) -> httpx.Response:
            b = json.loads(r.content)["input"]
            seen.append(len(b))
            return httpx.Response(200, json={"embeddings": [[0.0] * 768 for _ in b]})

        embed_ollama(["x"] * n, "nomic-embed-text", "http://o", 32, transport=httpx.MockTransport(h))
        assert seen == expect


@pytest.mark.parametrize("response", [
    httpx.Response(500, text="oops"),
    httpx.Response(200, text="not json"),
    httpx.Response(200, json={"embeddings": None}),
    httpx.Response(200, json={"embeddings": [[None] * 768]}),
    httpx.Response(200, json={"embeddings": [["a"] * 768]}),
    httpx.Response(200, json=[1, 2]),
])
def test_malformed_ollama_responses_raise_embed_error_after_three_attempts(response: httpx.Response) -> None:
    n, slept = {"n": 0}, []

    def h(r: httpx.Request) -> httpx.Response:
        n["n"] += 1
        return response

    with pytest.raises(EmbedError, match="3 attempts"):
        embed_ollama(["x"], "nomic-embed-text", "http://o", 32, sleep=slept.append, transport=httpx.MockTransport(h))
    assert n["n"] == 3 and slept == [1.0, 2.0]


def test_timeout_is_retried_like_any_http_error() -> None:
    n = {"n": 0}

    def h(r: httpx.Request) -> httpx.Response:
        n["n"] += 1
        if n["n"] < 3:
            raise httpx.ReadTimeout("slow")
        return httpx.Response(200, json={"embeddings": [[0.0] * 768]})

    out = embed_ollama(["x"], "nomic-embed-text", "http://o", 32, sleep=lambda s: None,
                       transport=httpx.MockTransport(h))
    assert len(out) == 1 and n["n"] == 3


def test_non_ascii_texts_are_sent_as_utf8_unchanged() -> None:
    got: list[str] = []

    def h(r: httpx.Request) -> httpx.Response:
        got.extend(json.loads(r.content)["input"])
        return httpx.Response(200, json={"embeddings": [[0.0] * 768 for _ in got]})

    embed_ollama(["日本語 café 😀"], "nomic-embed-text", "http://o", 32, transport=httpx.MockTransport(h))
    assert got == ["日本語 café 😀"]


def test_embed_rejects_wrong_dimension_from_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    import pipeline.embed as embedmod

    monkeypatch.setattr(embedmod, "embed_ollama", lambda *a, **k: [[0.0] * 384])
    with pytest.raises(ValueError, match="384"):
        embed(["x"], _settings(model="nomic-embed-text"))


def test_hashing_handles_non_ascii_and_huge_input() -> None:
    v = embed_hashing(["日本語 😀 !!!", "word " * 200_000])
    assert [len(x) for x in v] == [768, 768]
    assert all(abs(sum(a * a for a in x) - 1.0) < 1e-9 or not any(x) for x in v)  # unit or zero


# ---- run -------------------------------------------------------------------------------------

@pytest.fixture()
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeClient:
    c = FakeClient()
    monkeypatch.setattr(storemod, "get_client", lambda settings: c)
    return c


def test_colliding_chunk_ids_from_same_stem_fail_run_and_keep_live(tmp_path: Path, fake: FakeClient) -> None:
    (tmp_path / "x.md").write_text("---\ndoc_version: 1\n---\n# H\n\nalpha beta gamma.\n", encoding="utf-8")
    runmod.run_pipeline(_settings(str(tmp_path)))
    old = fake.cols["rahbar"]
    (tmp_path / "x.txt").write_text("# H\n\nalpha beta gamma.\n", encoding="utf-8")  # same stem "x"
    with pytest.raises(StoreError, match="duplicate"):
        runmod.run_pipeline(_settings(str(tmp_path)))
    assert list(fake.cols) == ["rahbar"] and fake.cols["rahbar"] is old


def test_documents_that_yield_no_chunks_fail_cleanly_with_exit_1(tmp_path: Path, fake: FakeClient,
                                                                 monkeypatch: pytest.MonkeyPatch,
                                                                 capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "blank.md").write_text("---\ndoc_version: 1\n---\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["run"])
    monkeypatch.setenv("CORPUS_DIR", str(tmp_path))
    monkeypatch.setenv("EMBED_MODEL", "hashing-bow-768")
    assert runmod.main() == 1
    out = [json.loads(ln) for ln in capsys.readouterr().out.splitlines() if ln.startswith("{")]
    assert any(r["msg"] == "indexer failed" for r in out) and fake.cols == {}


def test_unknown_model_fails_before_any_chroma_call(tmp_path: Path, fake: FakeClient) -> None:
    with pytest.raises(ValueError):
        runmod.run_pipeline(_settings(str(tmp_path), model="bogus"))
    assert fake.calls == []


def test_non_ascii_markdown_end_to_end(tmp_path: Path, fake: FakeClient) -> None:
    (tmp_path / "u.md").write_text("---\ndoc_version: 1\nsuperseded: true\n---\n# 1. Café\n\n"
                                   "日本語 text naïve 😀 attendance.\n", encoding="utf-8")
    runmod.run_pipeline(_settings(str(tmp_path)))
    col = fake.cols["rahbar"]
    assert "日本語" in col.docs[0] and col.metas[0]["superseded"] is True
