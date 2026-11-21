#!/usr/bin/env python3
"""Set `reviewed: true` for the given synthetic golden ids only (R12, D-144). Never touches `human` questions.

    python scripts/mark_reviewed.py g19 g20 ...
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

GOLDEN = Path(__file__).resolve().parents[1] / "eval" / "golden.jsonl"


def mark(ids: list[str], path: Path = GOLDEN) -> int:
    rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    by = {r["id"]: r for r in rows}
    for i in ids:
        if i not in by:
            raise SystemExit(f"unknown id {i}")
        if by[i]["origin"] != "synthetic":
            raise SystemExit(f"{i} is origin {by[i]['origin']!r}: only synthetic questions are marked reviewed")
    for i in ids:
        by[i]["reviewed"] = True
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return len(set(ids))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    print(f"marked {mark(sys.argv[1:])} questions reviewed")
