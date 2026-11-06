"""Ollama client and the embed dispatcher (phase 7 spec AC-6), with a fake HTTP layer."""

from __future__ import annotations

import json

import httpx
import pytest
from pipeline.config import IndexerSettings
from pipeline.embed import dimension, document_text, embed
from pipeline.embedding.ollama import EmbedError, embed_ollama
from pipeline.models import Chunk


def _transport(handler: object) -> httpx.MockTransport:
    return httpx.MockTransport(handler)  # type: ignore[arg-type]


def _ok(dim: int = 768) -> object:
    calls: list[list[str]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        assert req.url.path == "/api/embed" and body["model"] == "nomic-embed-text"
        calls.append(body["input"])
        return httpx.Response(200, json={"embeddings": [[float(len(t))] * dim for t in body["input"]]})

    handler.calls = calls  # type: ignore[attr-defined]
    return handler


def test_batches_and_order() -> None:
    h = _ok(4)
    texts = [f"t{'x' * i}" for i in range(7)]
    out = embed_ollama(texts, "nomic-embed-text", "http://o:1", 3, transport=_transport(h))
    assert [len(c) for c in h.calls] == [3, 3, 1]  # type: ignore[attr-defined]
    assert [v[0] for v in out] == [float(len(t)) for t in texts]


def test_retries_with_backoff_then_succeeds() -> None:
    n = {"i": 0}
    sleeps: list[float] = []

    def handler(req: httpx.Request) -> httpx.Response:
        n["i"] += 1
        if n["i"] < 3:
            return httpx.Response(500)
        return httpx.Response(200, json={"embeddings": [[1.0, 2.0]]})

    out = embed_ollama(["a"], "m", "http://o", 32, sleep=sleeps.append, transport=_transport(handler))
    assert out == [[1.0, 2.0]] and sleeps == [1.0, 2.0] and n["i"] == 3


def test_fails_after_three_attempts() -> None:
    n = {"i": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        n["i"] += 1
        raise httpx.ConnectError("down")

    with pytest.raises(EmbedError):
        embed_ollama(["a"], "m", "http://o", 32, sleep=lambda s: None, transport=_transport(handler))
    assert n["i"] == 3


@pytest.mark.parametrize("body", [{"embeddings": []}, {"nope": 1}, {"embeddings": [[1.0], [1.0]]}])
def test_wrong_count_or_shape_fails(body: dict[str, object]) -> None:
    with pytest.raises(EmbedError):
        embed_ollama(["a"], "m", "http://o", 32, sleep=lambda s: None,
                     transport=_transport(lambda r: httpx.Response(200, json=body)))


def test_second_batch_failure_fails_whole_stage() -> None:
    n = {"i": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        n["i"] += 1
        if n["i"] == 1:
            return httpx.Response(200, json={"embeddings": [[1.0]] * 2})
        return httpx.Response(503)

    with pytest.raises(EmbedError):
        embed_ollama(["a", "b", "c"], "m", "http://o", 2, sleep=lambda s: None, transport=_transport(handler))


def test_ragged_vectors_fail() -> None:
    seq = iter([[[1.0, 2.0]], [[1.0]]])
    with pytest.raises(EmbedError):
        embed_ollama(["a", "b"], "m", "http://o", 1,
                     transport=_transport(lambda r: httpx.Response(200, json={"embeddings": next(seq)})))


def _settings(model: str) -> IndexerSettings:
    return IndexerSettings(embed_model=model, chroma_host="h", chroma_port=1, collection="c",
                           corpus_dir="d", chunk_size=400, chunk_overlap=50, ollama_url="http://o")


def test_hashing_model_needs_no_network() -> None:
    out = embed(["search_document: s\ntext one", "x"], _settings("hashing-bow-768"))
    assert len(out) == 2 and len(out[0]) == 768


def test_unknown_model_rejected() -> None:
    with pytest.raises(ValueError, match="prefix rule"):
        embed(["a"], _settings("some-other-model"))
    assert dimension("nomic-embed-text:latest") == 768


def test_document_text_prefix_and_section() -> None:
    c = Chunk("id", "body text", "s.pdf", "1.21 Attendance", 3, "2026", False)
    assert document_text(c) == "search_document: 1.21 Attendance\nbody text"
