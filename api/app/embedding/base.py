"""The embedder interface (architecture 5.3). The api only ever embeds questions."""

from __future__ import annotations

from typing import Protocol


class EmbedError(RuntimeError):
    pass


class Embedder(Protocol):
    model: str

    def embed_query(self, question: str) -> list[float]:
        """One vector for the question, with the model's query prefix applied."""
        ...
