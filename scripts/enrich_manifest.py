#!/usr/bin/env python3
"""Add `family` to the real corpus manifest (architecture-a3 5.2), keeping the original.

    python scripts/enrich_manifest.py corpus/raw

Writes `_index.a02.json` (a byte copy of the original, only if absent) and rewrites `_index.json`
with a `family` per entry. `title` is not added: the loader falls back to `name`. Idempotent.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

FAMILIES = {
    "undergraduate-academic-rules-aug-2023.pdf": "academic-rules",
    "academic-rules-handbook-jun-2026.pdf": "academic-rules",
    "annual-report-2019-20.pdf": "annual-report",
    "annual-report-2023-24.pdf": "annual-report",
    "fee-structure-page.html": "fee-structure",
}


def enrich(corpus: Path) -> int:
    index = corpus / "_index.json"
    backup = corpus / "_index.a02.json"
    if not backup.exists():
        shutil.copyfile(index, backup)
    entries = json.loads(backup.read_text(encoding="utf-8"))
    for e in entries:
        e["family"] = FAMILIES.get(e["file"], Path(e["file"]).stem)
    index.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    return len(entries)


if __name__ == "__main__":
    print(f"enriched {enrich(Path(sys.argv[1] if len(sys.argv) > 1 else 'corpus/raw'))} entries")
