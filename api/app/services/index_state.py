"""The API's view of the live index (architecture 5.6.4, AD-20). Read-only.

The indexer swaps collections (delete + rename), so the collection *id* changes. This holds a
snapshot of the collection metadata and the handle, re-fetched by name at most every
INDEX_REFRESH_SECONDS and on demand. It also checks the embedding pin (5.3) and the vector dimension.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..config import Settings

log = logging.getLogger("rahbar.index_state")


class IndexUnavailable(RuntimeError):
    """Chroma down, collection missing or empty, or a pin or dimension conflict.

    `reason` is one of: chroma, collection, embed_pin, dimension. Phase 10 maps it to
    /readyz 503 (names the failed dependency) and to 503 {"detail": "index unavailable"}.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


@dataclass(frozen=True)
class Snapshot:
    index_id: str
    embed_model: str
    dimension: int
    doc_versions: list[str]
    chunk_count: int
    collection: Any   # the Chroma collection handle for this index_id; never used to write
    fetched_at: float


class IndexState:
    def __init__(self, settings: Settings, *, client: Any = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._s = settings
        self._client = client
        self._clock = clock
        self._lock = threading.Lock()
        self._snap: Snapshot | None = None
        self._problem: str | None = None
        self._pin_logged: set[str] = set()
        self._dim_checked: set[str] = set()
        self._dim_bad: set[str] = set()

    def _chroma(self) -> Any:
        if self._client is None:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            self._client = chromadb.HttpClient(host=self._s.chroma_host, port=self._s.chroma_port,
                                               settings=ChromaSettings(anonymized_telemetry=False))
        return self._client

    def _fetch(self) -> Snapshot:
        try:
            col = self._chroma().get_collection(self._s.collection)
            meta = dict(col.metadata or {})
            chunks = int(col.count())
        except Exception as exc:
            # chromadb raises NotFoundError (and, in older clients, ValueError) for a missing collection.
            missing = type(exc).__name__ in ("NotFoundError", "InvalidCollectionException") or (
                isinstance(exc, ValueError) and "does not exist" in str(exc))
            raise IndexUnavailable("collection" if missing else "chroma", repr(exc)) from exc
        if chunks == 0:
            raise IndexUnavailable("collection", "collection is empty")
        versions = sorted({str(d["doc_version"]) for d in json.loads(meta.get("doc_versions", "[]"))})
        return Snapshot(index_id=str(meta.get("index_id", "")), embed_model=str(meta.get("embed_model", "")),
                        dimension=int(meta.get("dimension", 0)), doc_versions=versions,
                        chunk_count=chunks, collection=col, fetched_at=self._clock())

    def get(self, *, force: bool = False) -> Snapshot:
        with self._lock:
            old = self._snap
            if old is not None and not force and self._clock() - old.fetched_at < self._s.index_refresh_seconds:
                return old
            try:
                snap = self._fetch()
            except IndexUnavailable as exc:
                self._problem = exc.reason
                if old is not None and exc.reason == "chroma":
                    # D-59: a blip must not break requests; the query itself fails honestly if Chroma is down.
                    log.warning("index refresh failed, serving the previous snapshot",
                                extra={"error": str(exc), "index_id": old.index_id})
                    return old
                raise
            self._snap = snap
            self._problem = None
            self._check_pin(snap)
            if self._problem is None and snap.index_id in self._dim_bad:
                self._problem = "dimension"
            return snap

    def _check_pin(self, snap: Snapshot) -> None:
        if snap.embed_model == self._s.embed_model:
            return
        self._problem = "embed_pin"
        if snap.index_id not in self._pin_logged:
            self._pin_logged |= {snap.index_id}
            log.error("embedding pin conflict", extra={
                "collection_embed_model": snap.embed_model, "api_embed_model": self._s.embed_model,
                "collection": self._s.collection,
                "action": "not ready until the indexer re-runs with the same model"})

    def require_pin(self, snap: Snapshot) -> None:
        if snap.embed_model != self._s.embed_model:
            raise IndexUnavailable("embed_pin", f"collection {snap.embed_model!r} vs api {self._s.embed_model!r}")

    def check_dimension(self, snap: Snapshot, n: int) -> None:
        """First query per index_id: the question vector must have the collection's dimension."""
        if snap.index_id in self._dim_checked:
            return
        if n != snap.dimension:
            self._problem = "dimension"
            self._dim_bad |= {snap.index_id}
            log.error("embedding dimension conflict", extra={
                "collection_dimension": snap.dimension, "query_dimension": n, "index_id": snap.index_id})
            raise IndexUnavailable("dimension", f"collection {snap.dimension} vs query {n}")
        self._dim_checked |= {snap.index_id}

    def problem(self) -> str | None:
        """None when healthy, else chroma | collection | embed_pin | dimension (for /readyz in phase 10)."""
        return self._problem
