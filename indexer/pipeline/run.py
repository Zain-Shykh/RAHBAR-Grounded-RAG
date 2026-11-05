"""The indexer Job's entry point. It runs once and exits (section 4.2).

    python -m pipeline.run --dummy    # week 1: three fake chunks, no model needed
    python -m pipeline.run            # the real pipeline: extract, clean, chunk, embed, store

Exit code 0 means the index was written; anything else fails the Job, and
Kubernetes retries it up to the Job's backoffLimit.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from .config import IndexerSettings, get_settings
from .models import Chunk
from .verify import VerifyError


def log(msg: str, **fields: object) -> None:
    print(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                      "logger": "rahbar.indexer", "msg": msg, **fields}), flush=True)


def _front_matter(path: Path) -> dict[str, str]:
    """Read `key: value` lines between leading '---' markers (used by eval/fixtures)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    meta: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta


def discover(corpus_dir: str) -> list[tuple[Path, str, bool]]:
    """List (path, doc_version, superseded) for every document to index.

    corpus/fetch.py writes _index.json next to the files it downloads; use it when
    present. Otherwise read Markdown front matter (the CI fixtures work this way).
    """
    root = Path(corpus_dir)
    index = root / "_index.json"
    if index.exists():
        entries = json.loads(index.read_text(encoding="utf-8"))
        return [(root / e["file"], str(e.get("doc_version", "unknown")),
                 bool(e.get("superseded", False))) for e in entries]
    found = []
    for path in sorted(root.glob("*")):
        if path.suffix.lower() not in {".pdf", ".md", ".html", ".txt"}:
            continue
        if path.name.lower().startswith("readme"):
            continue
        meta = _front_matter(path) if path.suffix.lower() == ".md" else {}
        found.append((path, meta.get("doc_version", "unknown"),
                      meta.get("superseded", "false").lower() == "true"))
    return found


def run_pipeline(settings: IndexerSettings) -> int:
    from .chunk import chunk
    from .clean import clean
    from .embed import dimension, document_text, embed, wait_for_ollama
    from .extract import extract
    from .store import store, wait_for_chroma
    from .verify import verify

    dimension(settings.embed_model)  # an unknown model fails before any wait
    wait_for_chroma(settings, settings.chroma_wait_seconds)
    wait_for_ollama(settings, settings.ollama_wait_seconds)
    if (Path(settings.corpus_dir) / "_index.json").exists():  # fixture dirs have none
        log("verified corpus", files=verify(settings.corpus_dir))
    documents = discover(settings.corpus_dir)
    if not documents:
        raise SystemExit(f"no documents found in {settings.corpus_dir}")
    all_chunks: list[Chunk] = []
    stored_words = source_words = 0
    for path, doc_version, superseded in documents:
        doc = clean(extract(str(path), doc_version, superseded))
        pieces = chunk(doc, settings.chunk_size, settings.chunk_overlap)
        words = sum(len(c.text.split()) for c in pieces)
        src = sum(len(p.text.split()) for p in doc.pages)
        stored_words, source_words = stored_words + words, source_words + src
        log("chunked", source=path.name, chunks=len(pieces), words=words, source_words=src,
            amplification=round(words / src, 2) if src else 0.0)
        if not pieces:
            log("document produced no chunks", source=path.name)
        all_chunks.extend(pieces)
    log("chunked total", documents=len(documents), chunks=len(all_chunks), words=stored_words,
        source_words=source_words,
        amplification=round(stored_words / source_words, 2) if source_words else 0.0)
    started = time.perf_counter()
    vectors = embed([document_text(c) for c in all_chunks], settings)
    log("embedded", vectors=len(vectors), model=settings.embed_model,
        batches=-(-len(vectors) // settings.embed_batch_size),
        seconds=round(time.perf_counter() - started, 1))
    return store(all_chunks, vectors, settings)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the RAHBAR index, then exit.")
    parser.add_argument("--dummy", action="store_true", help="write three fake chunks")
    args = parser.parse_args()
    settings = get_settings()
    log("indexer starting", dummy=args.dummy, embed_model=settings.embed_model,
        collection=settings.collection, chroma=f"{settings.chroma_host}:{settings.chroma_port}",
        pod=os.environ.get("HOSTNAME", "-"))
    started = time.perf_counter()
    try:
        if args.dummy:
            from .dummy import write_dummy_index
            from .store import get_client

            count = write_dummy_index(settings, get_client(settings))
        else:
            count = run_pipeline(settings)
    except VerifyError as exc:
        for problem in str(exc).split("\n"):
            log("corpus verification failed", problem=problem)
        return 1
    except NotImplementedError as exc:
        log("indexer stage not implemented yet", error=str(exc))
        return 2
    except (Exception, SystemExit) as exc:  # a failed Job must say why, as JSON
        log("indexer failed", error=repr(exc), kind=type(exc).__name__)
        return 1
    log("indexer finished", chunks=count, seconds=round(time.perf_counter() - started, 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
