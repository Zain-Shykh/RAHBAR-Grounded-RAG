"""Indexer configuration, from the same ConfigMap the API reads (section 4.1)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class IndexerSettings:
    embed_model: str        # EMBED_MODEL: must equal the API's value (section 4.4)
    chroma_host: str
    chroma_port: int
    collection: str
    corpus_dir: str         # where the documents and _index.json sit inside the Job's pod
    chunk_size: int
    chunk_overlap: int
    ollama_url: str
    embed_batch_size: int = 32
    chroma_wait_seconds: float = 120.0
    ollama_wait_seconds: float = 60.0
    lake_dir: str = "/lake"          # LAKE_DIR: registry, quarantine, archive, reports (Job-writable volume)
    index_mode: str = "full"          # INDEX_MODE: full (A02 behaviour, default) | incremental (ConfigMap sets it)
    verify_strict: bool = False       # VERIFY_STRICT: a quarantined document fails the run


def get_settings() -> IndexerSettings:
    return IndexerSettings(
        embed_model=os.environ.get("EMBED_MODEL", "nomic-embed-text"),
        chroma_host=os.environ.get("CHROMA_HOST", "chroma"),
        chroma_port=int(os.environ.get("CHROMA_PORT", 8000)),
        collection=os.environ.get("CHROMA_COLLECTION", "rahbar"),
        corpus_dir=os.environ.get("CORPUS_DIR", "/corpus"),
        chunk_size=int(os.environ.get("CHUNK_SIZE", 400)),
        chunk_overlap=int(os.environ.get("CHUNK_OVERLAP", 50)),
        ollama_url=os.environ.get("OLLAMA_URL", "http://host.minikube.internal:11434"),
        embed_batch_size=int(os.environ.get("EMBED_BATCH_SIZE", 32)),
        chroma_wait_seconds=float(os.environ.get("CHROMA_WAIT_SECONDS", 120)),
        ollama_wait_seconds=float(os.environ.get("OLLAMA_WAIT_SECONDS", 60)),
        lake_dir=os.environ.get("LAKE_DIR", "/lake"),
        index_mode=os.environ.get("INDEX_MODE", "full"),
        verify_strict=os.environ.get("VERIFY_STRICT", "false").lower() == "true",
    )
