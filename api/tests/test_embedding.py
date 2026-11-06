"""Embedder parity (AD-09) and the Ollama query call (phase 8 AC-5)."""

from __future__ import annotations

import json

import httpx
import pytest

from app.config import Settings
from app.embedding import EmbedError, get_embedder
from app.embedding.hashing import DIM, embed_one
from app.embedding.ollama import OllamaEmbedder

# Same numbers as indexer/tests/test_embed_hashing.py: this is the parity check.
GOLDEN_TEXT = "The attendance rule requires 75% attendance"
GOLDEN = [(517, -0.412859), (627, 0.412859), (647, -0.69903), (692, -0.412859)]


def test_golden_vector() -> None:
    v = embed_one(GOLDEN_TEXT)
    assert len(v) == DIM == 768
    assert [(i, round(x, 6)) for i, x in enumerate(v) if x] == GOLDEN


def test_hashing_adds_no_query_prefix() -> None:
    # The indexer's hashing embedder strips only the document prefix, so the query side adds none.
    e = get_embedder(Settings(embed_model="hashing-bow-768"))
    assert e.embed_query(GOLDEN_TEXT) == embed_one(GOLDEN_TEXT)


def test_unknown_model_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown EMBED_MODEL"):
        get_embedder(Settings(embed_model="other"))


def _embedder(handler, sleeps: list[float]) -> OllamaEmbedder:  # type: ignore[no-untyped-def]
    return OllamaEmbedder("nomic-embed-text", "http://x:11434/", sleep=sleeps.append,
                          transport=httpx.MockTransport(handler))


def test_ollama_sends_query_prefix() -> None:
    seen: dict[str, object] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen.update(json.loads(req.content), path=req.url.path)
        return httpx.Response(200, json={"embeddings": [[0.5, 0.25]]})

    assert _embedder(handler, []).embed_query("late fee?") == [0.5, 0.25]
    assert seen == {"model": "nomic-embed-text", "input": ["search_query: late fee?"], "path": "/api/embed"}


def test_ollama_retries_then_fails() -> None:
    sleeps: list[float] = []
    calls: list[int] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(500)

    with pytest.raises(EmbedError):
        _embedder(handler, sleeps).embed_query("q")
    assert len(calls) == 3 and sleeps == [1.0, 2.0]


def test_ollama_recovers_on_second_attempt() -> None:
    n: list[int] = []

    def handler(req: httpx.Request) -> httpx.Response:
        n.append(1)
        return httpx.Response(503) if len(n) == 1 else httpx.Response(200, json={"embeddings": [[1.0]]})

    assert _embedder(handler, []).embed_query("q") == [1.0]
