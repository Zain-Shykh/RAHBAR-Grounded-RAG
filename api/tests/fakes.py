"""In-memory stand-ins for Chroma, shared by the retrieval tests. No network."""

from __future__ import annotations

import json
from typing import Any


class NotFoundError(Exception):
    """Same class name as chromadb.errors.NotFoundError, which the code matches by name."""


class FakeCollection:
    def __init__(self, rows: list[dict[str, Any]], meta: dict[str, Any]) -> None:
        self.rows, self.metadata, self.queries = rows, meta, []
        self.fail_next: Exception | None = None

    def count(self) -> int:
        return len(self.rows)

    def query(self, **kw: Any) -> dict[str, Any]:
        self.queries.append(kw)
        if self.fail_next:
            exc, self.fail_next = self.fail_next, None
            raise exc
        rows = [r for r in self.rows if _match(r["md"], kw.get("where"))][: kw["n_results"]]
        return {"ids": [[r["id"] for r in rows]], "documents": [[r["text"] for r in rows]],
                "metadatas": [[r["md"] for r in rows]], "distances": [[r["dist"] for r in rows]]}


def _match(md: dict[str, Any], where: dict[str, Any] | None) -> bool:
    if not where:
        return True
    (field, cond), = where.items()
    return md[field] in cond["$in"] if isinstance(cond, dict) else md[field] == cond


class FakeClient:
    def __init__(self, col: FakeCollection | None) -> None:
        self.col, self.gets = col, 0
        self.error: Exception | None = None

    def get_collection(self, name: str) -> FakeCollection:
        self.gets += 1
        if self.error:
            raise self.error
        if self.col is None:
            raise NotFoundError(f"Collection {name} does not exist")
        return self.col


def row(cid: str, source: str, section: str, version: str, superseded: bool, dist: float,
        page: int = 1, text: str = "text") -> dict[str, Any]:
    return {"id": cid, "text": text, "dist": dist,
            "md": {"source": source, "section": section, "page": page, "doc_version": version,
                   "superseded": superseded}}


def meta(index_id: str = "idx-1", model: str = "hashing-bow-768", dim: int = 768) -> dict[str, Any]:
    versions = [{"source": "a.pdf", "doc_version": "2026-06", "superseded": False},
                {"source": "b.pdf", "doc_version": "2023-08", "superseded": True}]
    return {"index_id": index_id, "embed_model": model, "dimension": dim,
            "doc_versions": json.dumps(versions)}


def rows() -> list[dict[str, Any]]:
    return [row("c1", "a.pdf", "4.25", "2026-06", False, 0.2),
            row("c2", "b.pdf", "4.25", "2023-08", True, 0.3)]
