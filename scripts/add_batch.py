#!/usr/bin/env python3
"""Merge a batch of documents into the inbox manifest (the demo's "ingest documents you have not seen").

    python scripts/add_batch.py <batch dir> <existing _index.json or -> <merged out dir>

Copies the batch files to <out dir>, and writes <out dir>/_index.json = existing entries (replaced by file name when the
batch has the same file) + the batch's own `_index.json` entries, or, when the batch has none, entries built from the
files (sha256, bytes, title from the first Markdown heading or the file name, doc_version and date from front matter).
`make ingest-batch BATCH=dir` runs it and copies <out dir> into the corpus-data volume with kubectl cp.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

SUFFIXES = {".pdf", ".md", ".html", ".htm", ".txt"}


def front_matter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    meta: dict[str, str] = {}
    if lines and lines[0].strip() == "---":
        for ln in lines[1:]:
            if ln.strip() == "---":
                break
            k, _, v = ln.partition(":")
            meta[k.strip()] = v.strip()
    return meta


def entry_for(path: Path) -> dict:
    data = path.read_bytes()
    meta = front_matter(path) if path.suffix == ".md" else {}
    title = meta.get("title")
    if not title and path.suffix == ".md":
        first = next((ln.lstrip("# ").strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.startswith("#")), "")
        title = first or None
    e = {"file": path.name, "name": title or path.stem, "title": title or path.stem, "bytes": len(data),
         "sha256": hashlib.sha256(data).hexdigest(), "superseded": meta.get("superseded", "false") == "true",
         "family": meta.get("family") or path.stem, "url": "local://batch"}
    if meta.get("doc_version"):
        e["doc_version"] = meta["doc_version"]
    if meta.get("date"):
        e["date"] = meta["date"]
    return e


def main() -> int:
    batch, existing, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    merged: dict[str, dict] = {}
    if existing != "-" and Path(existing).is_file() and Path(existing).stat().st_size:
        merged = {e["file"]: e for e in json.loads(Path(existing).read_text())}
    mf = batch / "_index.json"
    new = json.loads(mf.read_text()) if mf.exists() else [entry_for(p) for p in sorted(batch.iterdir())
                                                           if p.suffix.lower() in SUFFIXES and not p.name.startswith("README")]
    for e in new:
        merged[e["file"]] = e
        shutil.copyfile(batch / e["file"], out / e["file"])
    (out / "_index.json").write_text(json.dumps(list(merged.values()), indent=2) + "\n")
    print(f"batch of {len(new)} files merged: manifest now lists {len(merged)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
