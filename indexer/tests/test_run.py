"""run_pipeline wiring, logs and exit codes (phase 7 spec AC-4, AC-7)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fakechroma import FakeClient
from pipeline import run as runmod
from pipeline import store as storemod
from pipeline.config import IndexerSettings
from pipeline.embed import wait_for_ollama


def _fixtures(tmp_path: Path, n: int = 2) -> Path:
    for i in range(n):
        (tmp_path / f"doc{i}.md").write_text(
            f"---\ndoc_version: 2026\nsuperseded: false\n---\n# Heading {i}\n\n" + f"word{i} alpha beta. " * 30,
            encoding="utf-8")
    return tmp_path


def _settings(corpus: Path) -> IndexerSettings:
    return IndexerSettings(embed_model="hashing-bow-768", chroma_host="h", chroma_port=1, collection="rahbar",
                           corpus_dir=str(corpus), chunk_size=50, chunk_overlap=5, ollama_url="http://o",
                           chroma_wait_seconds=0.0)


@pytest.fixture()
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeClient:
    c = FakeClient()
    monkeypatch.setattr(storemod, "get_client", lambda settings: c)
    return c


def _logs(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    return [json.loads(ln) for ln in capsys.readouterr().out.splitlines() if ln.startswith("{")]


def test_full_run_with_hashing_model(tmp_path: Path, fake: FakeClient, capsys: pytest.CaptureFixture[str]) -> None:
    n = runmod.run_pipeline(_settings(_fixtures(tmp_path)))
    col = fake.cols["rahbar"]
    assert n == col.count() > 2 and col.metadata["chunk_count"] == n
    assert {m["source"] for m in col.metas} == {"doc0.md", "doc1.md"}
    logs = _logs(capsys)
    msgs = [r["msg"] for r in logs]
    assert msgs.count("extracted") == 2 and msgs.count("chunked") == 2
    assert {"chunked total", "embedded", "stored"} <= set(msgs)
    total = next(r for r in logs if r["msg"] == "chunked total")
    assert total["chunks"] == n and "amplification" in total
    assert all("ts" in r and r["logger"] == "rahbar.indexer" for r in logs)
    assert any(r["msg"] == "extracted" and "ocr_pages" in r and "seconds" in r for r in logs)


def test_embed_failure_on_second_batch_keeps_live_index(tmp_path: Path, fake: FakeClient,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    corpus = _fixtures(tmp_path)
    runmod.run_pipeline(_settings(corpus))
    old = fake.cols["rahbar"]
    old_id = old.metadata["index_id"]
    from pipeline.embedding import hashing

    calls = {"n": 0}
    real = hashing.embed_hashing

    def flaky(texts: list[str]) -> list[list[float]]:
        calls["n"] += 1
        if calls["n"] > 1:
            raise RuntimeError("second batch failed")
        return real(texts)

    # a batching embedder that fails on its second batch
    import pipeline.embed as embedmod

    def batched(texts: list[str]) -> list[list[float]]:
        return [v for i in range(0, len(texts), 2) for v in flaky(texts[i:i + 2])]

    monkeypatch.setattr(embedmod, "embed_hashing", batched)
    with pytest.raises(RuntimeError):
        runmod.run_pipeline(_settings(corpus))
    assert list(fake.cols) == ["rahbar"] and fake.cols["rahbar"] is old
    assert old.metadata["index_id"] == old_id


def test_main_exit_codes(tmp_path: Path, fake: FakeClient, monkeypatch: pytest.MonkeyPatch,
                         capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.argv", ["run"])
    monkeypatch.setenv("CORPUS_DIR", str(_fixtures(tmp_path)))
    monkeypatch.setenv("EMBED_MODEL", "hashing-bow-768")
    monkeypatch.setenv("CHUNK_SIZE", "50")
    monkeypatch.setenv("CHUNK_OVERLAP", "5")
    assert runmod.main() == 0
    monkeypatch.setenv("EMBED_MODEL", "no-such-model")
    assert runmod.main() == 1
    assert any(r["msg"] == "indexer failed" for r in _logs(capsys))
    monkeypatch.setenv("EMBED_MODEL", "hashing-bow-768")
    monkeypatch.setenv("CORPUS_DIR", str(tmp_path / "empty"))
    (tmp_path / "empty").mkdir()
    assert runmod.main() == 1


def test_chroma_never_ready_exits_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                    capsys: pytest.CaptureFixture[str]) -> None:
    class Down:
        def heartbeat(self) -> int:
            raise ConnectionError("down")

    monkeypatch.setattr(storemod, "get_client", lambda s: Down())
    monkeypatch.setattr("sys.argv", ["run"])
    monkeypatch.setenv("CORPUS_DIR", str(_fixtures(tmp_path)))
    monkeypatch.setenv("EMBED_MODEL", "hashing-bow-768")
    monkeypatch.setenv("CHROMA_WAIT_SECONDS", "0")
    assert runmod.main() == 1
    assert any("Chroma not ready" in str(r.get("error")) for r in _logs(capsys))


def test_wait_for_ollama(tmp_path: Path) -> None:
    s = _settings(tmp_path)
    s2 = IndexerSettings(**{**s.__dict__, "embed_model": "nomic-embed-text"})

    def tags(models: list[str]) -> httpx.MockTransport:
        return httpx.MockTransport(lambda r: httpx.Response(200, json={"models": [{"name": m} for m in models]}))

    wait_for_ollama(s2, 0.0, transport=tags(["nomic-embed-text:latest", "llama3.2:3b"]))
    wait_for_ollama(s, 0.0, transport=tags([]))  # hashing: no wait at all
    with pytest.raises(TimeoutError, match="not in"):
        wait_for_ollama(s2, 0.0, transport=tags(["llama3.2:3b"]), sleep=lambda x: None)

    def down(r: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with pytest.raises(TimeoutError):
        wait_for_ollama(s2, 0.0, transport=httpx.MockTransport(down))


def test_dummy_still_writes_three_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    from pipeline.dummy import write_dummy_index

    class Col:
        def add(self, **kw: object) -> None:
            self.n = len(kw["ids"])  # type: ignore[arg-type]

        def count(self) -> int:
            return self.n

    class Cl:
        def delete_collection(self, n: str) -> None: ...
        def create_collection(self, **kw: object) -> Col:
            return Col()

    assert write_dummy_index(_settings(Path(".")), Cl()) == 3
