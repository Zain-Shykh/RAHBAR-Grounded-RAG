"""The manifest contract (architecture-a3 5.2): one entry per inbox file, with the fields A1 checks.

`_index.json` is written by corpus/fetch.py (Assignment 02) and may carry the optional fields
`title`, `date`, `family`, `pages`. Without a manifest (the CI fixtures) the Markdown front matter
is read instead. Old manifests stay valid: `discover()` in run.py is unchanged.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_SUFFIXES = {".pdf", ".md", ".html", ".htm", ".txt"}


@dataclass(frozen=True)
class Entry:
    file: str                 # also the document id (`source`)
    doc_version: str | None
    superseded: bool
    title: str | None
    date: str | None
    family: str               # versions of one document share it; default is the file name
    sha256: str | None
    bytes: int | None
    pages: int | None

    @property
    def has_version_or_date(self) -> bool:
        return bool((self.doc_version and self.doc_version != "unknown") or self.date)


def _front_matter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    meta: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta


def _entry(e: dict) -> Entry:
    ver = e.get("doc_version")
    return Entry(file=e["file"], doc_version=None if ver in (None, "") else str(ver),
                 superseded=bool(e.get("superseded", False)),
                 title=e.get("title") or e.get("name") or None, date=e.get("date") or None,
                 family=e.get("family") or e["file"], sha256=e.get("sha256"),
                 bytes=e.get("bytes"), pages=e.get("pages"))


def load_manifest(corpus_dir: str) -> list[Entry]:
    root = Path(corpus_dir)
    index = root / "_index.json"
    if index.exists():
        return [_entry(e) for e in json.loads(index.read_text(encoding="utf-8"))]
    out = []
    for path in sorted(root.glob("*")):
        if path.suffix.lower() not in _SUFFIXES or path.name.lower().startswith("readme"):
            continue
        meta = _front_matter(path) if path.suffix.lower() == ".md" else {}
        out.append(Entry(file=path.name, doc_version=meta.get("doc_version"),
                         superseded=meta.get("superseded", "false").lower() == "true",
                         title=meta.get("title"), date=meta.get("date"),
                         family=meta.get("family") or path.name, sha256=None, bytes=None, pages=None))
    return out
