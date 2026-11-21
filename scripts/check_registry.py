#!/usr/bin/env python3
"""Compare per-source chunk counts in Chroma with the registry (R3-AC10, I-21). Exit 1 on a difference or an orphan.

    python scripts/check_registry.py --chroma-host H --chroma-port P --collection NAME --registry PATH
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def compare(col: Any, docs: dict[str, dict]) -> tuple[list[str], bool]:
    """Table lines and ok. A source in Chroma but not in the registry is an orphan."""
    got = Counter(md["source"] for md in col.get(include=["metadatas"])["metadatas"])
    lines, ok = [f"{'source':<60} {'chroma':>7} {'registry':>8}  verdict"], True
    for s in sorted(set(got) | set(docs)):
        have, want = got.get(s, 0), docs[s]["chunks"] if s in docs else None
        verdict = "ORPHAN" if want is None else "ok" if have == want else "DIFF"
        ok &= verdict == "ok"
        lines.append(f"{s:<60} {have:>7} {'-' if want is None else want:>8}  {verdict}")
    return lines, ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chroma-host", default="localhost")
    ap.add_argument("--chroma-port", type=int, default=8100)
    ap.add_argument("--collection", default="rahbar")
    ap.add_argument("--registry", required=True)
    a = ap.parse_args()
    import chromadb
    from chromadb.config import Settings
    client = chromadb.HttpClient(host=a.chroma_host, port=a.chroma_port, settings=Settings(anonymized_telemetry=False))
    docs = json.loads(Path(a.registry).read_text(encoding="utf-8"))["docs"]
    lines, ok = compare(client.get_collection(a.collection), docs)
    print("\n".join(lines))
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
