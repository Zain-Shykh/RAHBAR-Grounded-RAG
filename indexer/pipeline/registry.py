"""The registry: what is indexed, per collection (architecture-a3 5.4). Written atomically, after the swap."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


class Registry:
    def __init__(self, path: Path, data: dict[str, Any] | None = None) -> None:
        self.path = path
        self.data: dict[str, Any] = data or {"schema": 1, "docs": {}, "quarantined": {}}

    @classmethod
    def load(cls, lake_root: str | Path, collection: str) -> Registry:
        path = Path(lake_root) / "registry" / f"{collection}.json"
        if path.exists():
            return cls(path, json.loads(path.read_text(encoding="utf-8")))
        return cls(path)

    @property
    def exists(self) -> bool:
        return self.path.exists()

    @property
    def docs(self) -> dict[str, dict]:
        return self.data["docs"]

    @property
    def quarantined(self) -> dict[str, dict]:
        return self.data["quarantined"]

    def settings_diff(self, *, embed_model: str, dimension: int, chunk_size: int, chunk_overlap: int) -> list[str]:
        """Differences that forbid incremental mode (I-3, A3-R1). Empty for a fresh registry."""
        if not self.docs:
            return []
        want = {"embed_model": embed_model, "dimension": dimension, "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap}
        return [f"{k}: registry has {self.data.get(k)!r}, now {v!r}" for k, v in want.items()
                if self.data.get(k) != v]

    def save(self, **meta: Any) -> None:
        self.data.update(meta)
        self.data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(self.data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    def total_chunks(self) -> int:
        return sum(d["chunks"] for d in self.docs.values())
