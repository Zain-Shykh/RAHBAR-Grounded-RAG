"""Stage 5: Store. The only code in the whole system that writes to Chroma (architecture 5.4.4)."""

from __future__ import annotations

import json
import secrets
import time
from collections.abc import Callable
from typing import Any

from .config import IndexerSettings
from .embed import dimension
from .models import Chunk
from .run import log

STAGING_SUFFIX = "_next"
ADD_BATCH = 500


class StoreError(RuntimeError):
    pass


def get_client(settings: IndexerSettings) -> Any:
    import chromadb  # the thin client, from chromadb-client in requirements.txt
    from chromadb.config import Settings as ChromaSettings

    return chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port,
                               settings=ChromaSettings(anonymized_telemetry=False))


def wait_for_chroma(settings: IndexerSettings, timeout: float, *, client: Any = None,
                    sleep: Callable[[float], None] = time.sleep) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            (client or get_client(settings)).heartbeat()
            return
        except Exception as exc:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Chroma not ready after {timeout:.0f} s: {exc!r}") from exc
            sleep(2.0)


def validate(chunks: list[Chunk], vectors: list[list[float]], model: str) -> None:
    if len(chunks) != len(vectors):
        raise StoreError(f"{len(chunks)} chunks but {len(vectors)} vectors")
    if not chunks:
        raise StoreError("no chunks to store")
    ids = [c.id for c in chunks]
    if len(set(ids)) != len(ids):
        dup = sorted({i for i in ids if ids.count(i) > 1})[:3]
        raise StoreError(f"duplicate chunk ids, for example {dup}")
    empty = [c.id for c in chunks if not c.text.strip()]
    if empty:
        raise StoreError(f"empty chunk text, for example {empty[:3]}")
    dim = dimension(model)
    if {len(v) for v in vectors} != {dim}:
        raise StoreError(f"vector length is not {dim} for {model}")


def _delete(client: Any, name: str) -> None:
    try:
        client.delete_collection(name)
    except Exception:  # did not exist
        pass


def _exists(client: Any, name: str) -> bool:
    try:
        client.get_collection(name)
        return True
    except Exception:
        return False


def _doc_versions(chunks: list[Chunk]) -> str:
    seen = {(c.source, c.doc_version, c.superseded) for c in chunks}
    return json.dumps([{"source": s, "doc_version": v, "superseded": sup} for s, v, sup in sorted(seen)])


def store(chunks: list[Chunk], vectors: list[list[float]], settings: IndexerSettings,
          client: Any = None) -> int:
    """Stage-and-swap (AD-02). Any failure before the old collection is deleted leaves it untouched."""
    started = time.perf_counter()
    validate(chunks, vectors, settings.embed_model)
    client = client or get_client(settings)
    live, staging = settings.collection, settings.collection + STAGING_SUFFIX
    now = time.gmtime()
    index_id = f"{time.strftime('%Y%m%dT%H%M%SZ', now)}-{secrets.token_hex(3)}"
    _delete(client, staging)
    try:
        col = client.create_collection(name=staging, metadata={
            "hnsw:space": "cosine", "embed_model": settings.embed_model,
            "dimension": len(vectors[0]), "index_id": index_id,
            "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", now), "chunk_count": len(chunks),
            "chunk_size": settings.chunk_size, "chunk_overlap": settings.chunk_overlap,
            "doc_versions": _doc_versions(chunks)})
        for i in range(0, len(chunks), ADD_BATCH):
            part = slice(i, i + ADD_BATCH)
            col.add(ids=[c.id for c in chunks[part]], documents=[c.text for c in chunks[part]],
                    embeddings=vectors[part], metadatas=[c.metadata() for c in chunks[part]])
        if col.count() != len(chunks):
            raise StoreError(f"staged {col.count()} records, expected {len(chunks)}")
    except BaseException:
        _delete(client, staging)  # `live` was never touched
        raise
    existed = _exists(client, live)
    _delete(client, live)
    col.modify(name=live)  # no metadata argument: the rename keeps it (A-2)
    log("stored", chunks=len(chunks), index_id=index_id, collection=live,
        replaced=existed, seconds=round(time.perf_counter() - started, 1))
    return len(chunks)
