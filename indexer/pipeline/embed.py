"""Stage 4: Embed. One vector per chunk, from the pinned model only (architecture 5.3)."""

from __future__ import annotations

import time
from collections.abc import Callable

import httpx

from .config import IndexerSettings
from .embedding.hashing import MODEL as HASHING_MODEL
from .embedding.hashing import embed_hashing
from .embedding.ollama import embed_ollama
from .models import Chunk

NOMIC = "nomic-embed-text"
DIMENSIONS = {NOMIC: 768, HASHING_MODEL: 768}


def dimension(model: str) -> int:
    for name, dim in DIMENSIONS.items():
        if model.startswith(name):
            return dim
    raise ValueError(f"unknown EMBED_MODEL {model!r}: write its prefix rule into architecture 5.3 first")


def document_text(chunk: Chunk) -> str:
    """The text that is embedded (AD-23). The stored document is chunk.text only."""
    return f"search_document: {chunk.section}\n{chunk.text}"


def embed(texts: list[str], settings: IndexerSettings) -> list[list[float]]:
    """Embed already-prefixed texts with settings.embed_model and nothing else."""
    model = settings.embed_model
    dimension(model)  # unknown model -> ValueError
    if model == HASHING_MODEL:
        vectors = embed_hashing(texts)
    else:
        vectors = embed_ollama(texts, model, settings.ollama_url, settings.embed_batch_size)
    bad = {len(v) for v in vectors} - {dimension(model)}
    if bad:
        raise ValueError(f"vector length {sorted(bad)} differs from the model dimension {dimension(model)}")
    return vectors


def wait_for_ollama(settings: IndexerSettings, timeout: float, *,
                    sleep: Callable[[float], None] = time.sleep,
                    transport: httpx.BaseTransport | None = None) -> None:
    """Wait until GET /api/tags lists the embedding model. Not needed for the hashing model."""
    if settings.embed_model == HASHING_MODEL:
        return
    want = settings.embed_model
    deadline = time.monotonic() + timeout
    while True:
        try:
            with httpx.Client(timeout=5.0, transport=transport) as client:
                names = [m.get("name", "") for m in client.get(f"{settings.ollama_url.rstrip('/')}/api/tags").json()["models"]]
            if any(n == want or (":" not in want and n == f"{want}:latest") for n in names):
                return
            problem = f"model {want!r} not in {names}"
        except Exception as exc:
            problem = repr(exc)
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Ollama not ready after {timeout:.0f} s: {problem}")
        sleep(2.0)
