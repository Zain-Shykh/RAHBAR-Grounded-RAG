#!/usr/bin/env python3
"""I-25 for Assignment 03: every decimal number quoted in docs/report/report.md must come from a committed file.

    python scripts/check_numbers_a3.py [report.md]      exit 0 all matched, 1 unmatched numbers listed

Corpus searched: eval/results, docs/evidence, traces, docs/specs, eval/gate.yaml, eval/coverage.yaml, corpus/batch_b/PLANTED.json
(text of every committed file there). A decimal in the report (e.g. 0.7949, 54.4, 285.3) matches when
  1. the same digits occur as a number in some file ("0.7949" or "0.79490"), or
  2. some number in a file, rounded half-up to the report's number of decimals, equals it (0.79487 -> 0.7949; 181.66 -> 181.7), or
  3. it equals a difference or a sum of two numbers in the same file is NOT allowed (derived numbers must be in a file: the
     scripts that derive them write them, e.g. drift_report.py).
Integers are not checked (counts such as 50 or 6 are verified against the same files by the tester), nor are version-like
tokens (3.2.3), dates and file names: the report text is stripped of code spans of the form `...` that hold file names and ids,
but a decimal inside a code span is still checked.
Differences written with a sign (+0.0147) are checked by absolute value.
"""
from __future__ import annotations

import re
import subprocess
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

R = Path(__file__).resolve().parents[1]
SRC = ["eval/results", "docs/evidence", "traces", "docs/specs", "eval/gate.yaml", "eval/coverage.yaml", "corpus/batch_b/PLANTED.json"]
NUM = re.compile(r"(?<![\w.])\d+\.\d+(?![\w.]|\.\d)")


def tracked() -> list[Path]:
    out = subprocess.run(["git", "ls-files", *SRC], cwd=R, capture_output=True, text=True, check=True).stdout.split()
    return [R / p for p in out if not p.endswith((".png", ".pdf"))]


def build() -> tuple[set[str], list[Decimal]]:
    lit: set[str] = set()
    vals: set[Decimal] = set()
    for p in tracked():
        try:
            txt = p.read_text(errors="ignore")
        except OSError:
            continue
        for m in NUM.finditer(txt):
            lit.add(m.group(0))
            vals.add(Decimal(m.group(0)))
    return lit, sorted(vals)


def matched(tok: str, lit: set[str], vals: list[Decimal], cache: dict[int, set[Decimal]]) -> bool:
    if tok in lit:
        return True
    d = len(tok.split(".")[1])
    if d not in cache:
        q = Decimal(1).scaleb(-d)
        cache[d] = {v.quantize(q, rounding=ROUND_HALF_UP) for v in vals}
    return Decimal(tok) in cache[d]


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else R / "docs/report/report.md"
    text = path.read_text()
    text = re.sub(r"\(https?://[^)]*\)", "", text)
    text = re.sub(r"\b\d{1,2}\.\d{1,2}\.\d{1,2}\b", "", text)              # 4.2.2 style references
    text = re.sub(r"\d{8}T\d{6}Z", "", text)                                  # run ids
    lit, vals = build()
    cache: dict[int, set[Decimal]] = {}
    bad = []
    for ln, line in enumerate(text.splitlines(), 1):
        for m in NUM.finditer(line):
            if not matched(m.group(0), lit, vals, cache):
                bad.append((ln, m.group(0), line.strip()[:90]))
    n = sum(len(NUM.findall(ln)) for ln in text.splitlines())
    print(f"{path.name}: {n} decimal numbers, {len(bad)} unmatched, searched {len(lit)} distinct literals in {len(tracked())} files")
    for b in bad:
        print(f"  line {b[0]}: {b[1]}   {b[2]}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
