from __future__ import annotations

from ..config import Settings
from .base import Embedder, EmbedError

__all__ = ["Embedder", "EmbedError", "get_embedder"]

_NOMIC = "nomic-embed-text"


class _Hashing:
    """hashing-bow-768: offline, for CI (architecture 5.3). The prefix is ignored."""

    def __init__(self, model: str) -> None:
        self.model = model

    def embed_query(self, question: str) -> list[float]:
        from .hashing import embed_one

        return embed_one(question)


def get_embedder(settings: Settings) -> Embedder:
    from .hashing import MODEL

    model = settings.embed_model
    if model == MODEL:
        return _Hashing(model)
    if model.startswith(_NOMIC):
        from .ollama import OllamaEmbedder

        return OllamaEmbedder(model, settings.ollama_url)
    raise ValueError(f"unknown EMBED_MODEL {model!r}: write its prefix rule into architecture 5.3 first")
