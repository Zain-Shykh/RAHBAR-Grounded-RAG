"""Ollama embeddings: POST {url}/api/embed (architecture 5.3). All-or-nothing."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

ATTEMPTS = 3
BACKOFF = (1.0, 2.0)  # seconds slept before attempt 2 and 3


class EmbedError(RuntimeError):
    pass


def _post(client: httpx.Client, url: str, model: str, batch: list[str],
          sleep: Callable[[float], None]) -> list[list[float]]:
    last: Exception | None = None
    for attempt in range(ATTEMPTS):
        if attempt:
            sleep(BACKOFF[attempt - 1])
        try:
            r = client.post(f"{url.rstrip('/')}/api/embed", json={"model": model, "input": batch})
            r.raise_for_status()
            vecs: Any = r.json()["embeddings"]
            if len(vecs) != len(batch):
                raise EmbedError(f"asked for {len(batch)} vectors, got {len(vecs)}")
            return [[float(x) for x in v] for v in vecs]
        except (httpx.HTTPError, KeyError, ValueError, TypeError, EmbedError) as exc:
            last = exc
    raise EmbedError(f"embedding batch failed after {ATTEMPTS} attempts: {last!r}")


def embed_ollama(texts: list[str], model: str, url: str, batch_size: int, *,
                 sleep: Callable[[float], None] = time.sleep,
                 transport: httpx.BaseTransport | None = None) -> list[list[float]]:
    out: list[list[float]] = []
    with httpx.Client(timeout=120.0, transport=transport) as client:
        for i in range(0, len(texts), batch_size):
            out.extend(_post(client, url, model, texts[i:i + batch_size], sleep))
    if out and len({len(v) for v in out}) != 1:
        raise EmbedError("vectors have different lengths")
    return out
