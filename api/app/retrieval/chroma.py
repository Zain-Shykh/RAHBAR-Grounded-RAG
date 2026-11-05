"""The real retriever (architecture 5.6.1, AD-20). Read-only: it only ever calls `query`.

Embeds the question with the pinned model, queries the live collection under the scope's
`where`, and maps each hit to a Passage with score = 1 - cosine distance. If the indexer swaps
the collection mid-request, it re-resolves the collection once and retries.
"""

from __future__ import annotations

import logging
from typing import Any

from ..config import Settings
from ..embedding import Embedder, get_embedder
from ..schemas import Passage
from ..services.index_state import IndexState, IndexUnavailable

log = logging.getLogger("rahbar.retrieval")


def _is_not_found(exc: Exception) -> bool:
    return type(exc).__name__ in ("NotFoundError", "InvalidCollectionException") or (
        isinstance(exc, ValueError) and "does not exist" in str(exc))


class ChromaRetriever:
    name = "chroma"

    def __init__(self, settings: Settings, *, state: IndexState | None = None,
                 embedder: Embedder | None = None) -> None:
        self.settings = settings
        self.embed_error = ""
        try:
            self.embedder: Embedder | None = embedder or get_embedder(settings)
        except ValueError as exc:
            # An unknown EMBED_MODEL must leave the pod not ready (the pin check names it), not crash it.
            self.embedder, self.embed_error = None, str(exc)
        self.state = state or IndexState(settings)

    def retrieve(self, question: str, k: int, *, vector: list[float] | None = None,
                 where: dict[str, Any] | None = None) -> list[Passage]:
        snap = self.state.get()
        self.state.require_pin(snap)
        if vector is None:
            if self.embedder is None:
                raise IndexUnavailable("embed_pin", self.embed_error)
            vector = self.embedder.embed_query(question)
        self.state.check_dimension(snap, len(vector))
        try:
            res = self._query(snap.collection, vector, k, where)
        except Exception as exc:
            if not _is_not_found(exc):
                raise IndexUnavailable("chroma", repr(exc)) from exc
            log.info("collection not found, re-resolving once", extra={"index_id": snap.index_id})
            snap = self.state.get(force=True)
            self.state.require_pin(snap)
            self.state.check_dimension(snap, len(vector))
            try:
                res = self._query(snap.collection, vector, k, where)
            except Exception as exc2:
                raise IndexUnavailable("chroma", repr(exc2)) from exc2
        return self._passages(res)

    @staticmethod
    def _query(collection: Any, vector: list[float], k: int, where: dict[str, Any] | None) -> Any:
        kwargs: dict[str, Any] = {"query_embeddings": [vector], "n_results": k,
                                  "include": ["documents", "metadatas", "distances"]}
        if where:
            kwargs["where"] = where
        return collection.query(**kwargs)

    @staticmethod
    def _passages(res: Any) -> list[Passage]:
        out: list[Passage] = []
        for cid, doc, md, dist in zip(res["ids"][0], res["documents"][0], res["metadatas"][0],
                                      res["distances"][0], strict=True):
            page = md.get("page")
            out.append(Passage(chunk_id=cid, text=doc, source=md["source"], section=md["section"],
                               page=page if isinstance(page, int) and page > 0 else None,
                               score=1.0 - float(dist)))
        return out
