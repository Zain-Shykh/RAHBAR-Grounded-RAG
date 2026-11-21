"""Rollback (R3-A2-4): make an older, superseded version current again, with zero embeddings.

    python -m pipeline.restore --source undergraduate-academic-rules-aug-2023.pdf --supersede <newer file>

The registry's `status` is the desired state; the copy-forward swap applies it to the chunk metadata.
The restored document is pinned so a later run does not supersede it again.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from .config import IndexerSettings, get_settings
from .incremental import run_incremental
from .registry import Registry
from .verification.lake import Lake


def restore(settings: IndexerSettings, source: str, *, supersede: str | None = None, client: Any = None,
            lake: Lake | None = None) -> dict:
    lake = lake or Lake(settings.lake_dir)
    reg = Registry.load(lake.root, settings.collection)
    if source not in reg.docs:
        raise SystemExit(f"{source} is not in the registry of {settings.collection}")
    reg.docs[source].update(status="active", pinned=True)
    if supersede:
        if supersede not in reg.docs:
            raise SystemExit(f"{supersede} is not in the registry of {settings.collection}")
        reg.docs[supersede]["status"] = "superseded"
    reg.save()
    return run_incremental(settings, client=client, lake=lake)


def main() -> int:
    ap = argparse.ArgumentParser(description="Restore a superseded document version.")
    ap.add_argument("--source", required=True)
    ap.add_argument("--supersede", help="the newer document to supersede in exchange")
    a = ap.parse_args()
    print(restore(get_settings(), a.source, supersede=a.supersede))
    return 0


if __name__ == "__main__":
    sys.exit(main())
