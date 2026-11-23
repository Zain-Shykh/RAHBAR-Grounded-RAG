#!/usr/bin/env python3
"""The release decision, kept apart from the release (R3-C2, R3-F3).

    python scripts/release_guard.py record <collection> <gate-file>   # write the gate verdict for a collection
    python scripts/release_guard.py check  <collection>               # exit 0 only if the recorded verdict is PASS

`make release` runs `check` first, so a candidate the gate rejected (or one that never went through the gate) is
refused. `FORCE=1` skips the check on purpose (the rollback drill); the target says so loudly.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

DECISIONS = Path(__file__).resolve().parents[1] / "eval" / "results" / "release-decisions.json"


def load() -> dict:
    return json.loads(DECISIONS.read_text()) if DECISIONS.exists() else {}


def verdict_of(gate_text: str) -> str:
    if re.search(r"^GATE PASSED", gate_text, re.M):
        return "PASS"
    if re.search(r"^GATE FAILED", gate_text, re.M):
        return "FAIL"
    raise SystemExit("not a gate result file: no 'GATE PASSED' or 'GATE FAILED' line")


def record(collection: str, gate_file: str) -> int:
    text = Path(gate_file).read_text()
    cand = re.search(r"^candidate (\S+)", text, re.M)
    d = load()
    d[collection] = {"verdict": verdict_of(text), "gate_file": gate_file, "candidate_result": cand.group(1) if cand else None,
                     "recorded": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    DECISIONS.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n")
    print(f"{collection}: gate {d[collection]['verdict']} ({gate_file})")
    return 0


def check(collection: str) -> int:
    e = load().get(collection)
    if e is None:
        print(f"RELEASE REFUSED: {collection} has no recorded gate result. Run the eval Job against it, then "
              f"`python scripts/release_guard.py record {collection} <gate file>`.")
        return 1
    if e["verdict"] != "PASS":
        print(f"RELEASE REFUSED: the gate rejected {collection} (see {e['gate_file']}). It is never rolled out.")
        return 1
    print(f"gate PASSED for {collection} ({e['gate_file']}): release allowed")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) == 4 and argv[1] == "record":
        return record(argv[2], argv[3])
    if len(argv) == 3 and argv[1] == "check":
        return check(argv[2])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
