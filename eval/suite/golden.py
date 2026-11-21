"""Load and validate eval/golden.jsonl (R3-B-1, R3-B-2). `python -m eval.suite.golden --check`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
MINIMUMS = {"questions": 25, "answerable": 15, "unanswerable": 5, "hard": 5, "human": 8, "synthetic_reviewed": 8}


def load(path: Path | str = HERE / "golden.jsonl", subset: str = "all") -> list[dict]:
    """subset: `all`, `A` (the corpus before Batch B) or `B`."""
    rows = []
    for n, ln in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if ln.strip():
            try:
                rows.append(json.loads(ln))
            except json.JSONDecodeError:
                rows.append({"id": f"line{n}", "_bad_json": True})  # reported by problems(), never a crash
    if subset != "all":
        rows = [r for r in rows if r.get("batch", "A") == subset]
    return rows


def counts(rows: list[dict]) -> dict[str, int]:
    return {
        "questions": len(rows),
        "answerable": sum(r.get("kind") == "answerable" for r in rows),
        "unanswerable": sum(r.get("kind") == "unanswerable" for r in rows),
        "hard": sum(bool(r.get("hard")) for r in rows),
        "human": sum(r.get("origin") == "human" for r in rows),
        "synthetic": sum(r.get("origin") == "synthetic" for r in rows),
        "synthetic_reviewed": sum(r.get("origin") == "synthetic" and bool(r.get("reviewed")) for r in rows),
        "batch_b": sum(r.get("batch") == "B" for r in rows),
    }


def problems(rows: list[dict]) -> list[str]:
    out = []
    ids = [r.get("id") for r in rows]
    if len(set(ids)) != len(ids):
        out.append("duplicate ids")
    for r in rows:
        if r.get("_bad_json"):
            out.append(f"{r['id']}: not valid JSON")
            continue
        if r.get("origin") not in ("human", "synthetic"):
            out.append(f"{r.get('id')}: origin must be human or synthetic")
        if r.get("kind") not in ("answerable", "unanswerable"):
            out.append(f"{r.get('id')}: kind must be answerable or unanswerable")
        elif r["kind"] == "answerable":
            if not r.get("relevant"):
                out.append(f"{r['id']}: answerable without a ground-truth document")
            for rel in r.get("relevant") or []:
                if not (rel.get("source") and rel.get("section") and isinstance(rel.get("page"), int)):
                    out.append(f"{r['id']}: relevant needs source, section and page")
        elif r.get("relevant"):
            out.append(f"{r['id']}: unanswerable must have no relevant passage")
    c = counts(rows)
    for key, minimum in MINIMUMS.items():
        if c[key] < minimum:
            out.append(f"{key}: {c[key]} < required {minimum}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--golden", default=str(HERE / "golden.jsonl"))
    ap.add_argument("--out")
    a = ap.parse_args()
    rows = load(a.golden)
    c, p = counts(rows), problems(rows)
    print(json.dumps(c))
    for m in p:
        print("PROBLEM:", m)
    if a.out:
        Path(a.out).write_text(json.dumps({"counts": c, "problems": p, "minimums": MINIMUMS}, indent=2) + "\n")
    return 1 if (a.check and p) else 0


if __name__ == "__main__":
    sys.exit(main())
