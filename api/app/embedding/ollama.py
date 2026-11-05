"""Ollama query embeddings: POST {url}/api/embed (architecture 5.3). Same call as the indexer's."""

from __future__ import annotations

import time
from collections.abc import Callable

import httpx

from .base import EmbedError

ATTEMPTS = 3
BACKOFF = (1.0, 2.0)  # seconds slept before attempt 2 and 3
QUERY_PREFIX = "search_query: "


class OllamaEmbedder:
    def __init__(self, model: str, url: str, *, timeout: float = 30.0,
                 sleep: Callable[[float], None] = time.sleep,
                 transport: httpx.BaseTransport | None = None) -> None:
        self.model = model
        self._url = url.rstrip("/")
        self._sleep = sleep
        self._client = httpx.Client(timeout=timeout, transport=transport)

    def embed_query(self, question: str) -> list[float]:
        last: Exception | None = None
        for attempt in range(ATTEMPTS):
            if attempt:
                self._sleep(BACKOFF[attempt - 1])
            try:
                r = self._client.post(f"{self._url}/api/embed",
                                      json={"model": self.model, "input": [QUERY_PREFIX + question]})
                r.raise_for_status()
                vecs = r.json()["embeddings"]
                if len(vecs) != 1:
                    raise EmbedError(f"asked for 1 vector, got {len(vecs)}")
                return [float(x) for x in vecs[0]]
            except (httpx.HTTPError, KeyError, ValueError, TypeError, EmbedError) as exc:
                last = exc
        raise EmbedError(f"query embedding failed after {ATTEMPTS} attempts: {last!r}")
