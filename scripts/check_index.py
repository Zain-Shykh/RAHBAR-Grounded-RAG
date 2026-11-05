"""Check the live collection after an indexer run (phase 7 spec AC-2, AC-3). Not part of the image.

    .venv/bin/python scripts/check_index.py [--port 8100] [--collection rahbar]
        [--not-index-id ID]     # fail when index_id is still ID (a re-run must change it)

Prints the collection metadata and chunks per source. Exits 1 on any failed check.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter

import chromadb
from chromadb.config import Settings

KEYS = {"hnsw:space", "embed_model", "dimension", "index_id", "built_at", "chunk_count",
        "chunk_size", "chunk_overlap", "doc_versions"}
FIELDS = {"source", "section", "page", "doc_version", "superseded"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=8100)
    ap.add_argument("--collection", default="rahbar")
    ap.add_argument("--not-index-id", default="")
    a = ap.parse_args()
    client = chromadb.HttpClient(host=a.host, port=a.port, settings=Settings(anonymized_telemetry=False))
    problems: list[str] = []
    names = [getattr(c, "name", c) for c in client.list_collections()]
    print("collections:", names)
    if a.collection + "_next" in names:
        problems.append(f"{a.collection}_next left behind")
    col = client.get_collection(a.collection)
    meta = dict(col.metadata or {})
    print(json.dumps({k: v for k, v in meta.items() if k != "doc_versions"}, indent=2))
    print("doc_versions:", len(json.loads(meta.get("doc_versions", "[]"))), "documents")
    if KEYS - set(meta):
        problems.append(f"missing metadata keys {sorted(KEYS - set(meta))}")
    n = col.count()
    if meta.get("chunk_count") != n:
        problems.append(f"chunk_count {meta.get('chunk_count')} != count() {n}")
    got = col.get(include=["metadatas", "embeddings", "documents"], limit=n + 1)
    per_source: Counter[str] = Counter()
    for md, emb, doc in zip(got["metadatas"], got["embeddings"], got["documents"], strict=True):
        if set(md) != FIELDS:
            problems.append(f"record fields {sorted(md)}")
            break
        if len(emb) != meta.get("dimension") or not doc.strip():
            problems.append("bad dimension or empty document")
            break
        per_source[md["source"]] += 1
    if len(set(got["ids"])) != len(got["ids"]):
        problems.append("duplicate ids")
    for s, c in sorted(per_source.items()):
        print(f"  {c:>5}  {s}")
    print(f"records {n}, sources {len(per_source)}")
    if a.not_index_id and meta.get("index_id") == a.not_index_id:
        problems.append("index_id did not change")
    for p in problems:
        print("FAIL", p)
    print("PASS" if not problems else "FAIL")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
