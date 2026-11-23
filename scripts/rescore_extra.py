#!/usr/bin/env python3
"""Apply the extra end-to-end checks (gold citation rate, abstained-with-text) to a finished result file, no model calls.

    python scripts/rescore_extra.py eval/results/suite-<ts>-<label>.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.suite.e2e_level import extra_metrics  # noqa: E402
from eval.suite.golden import load  # noqa: E402


def main(path: str) -> int:
    res = json.loads(Path(path).read_text())
    x = extra_metrics(res["e2e"]["per_question"], load(ROOT / "eval" / "golden.jsonl", "every"))
    print(f"{path}")
    print(f"gold_citation_rate {x['gold_citation_rate']:.4f} over {x['gold_citation_n']} answered answerable questions; misses: {x['gold_citation_misses']}")
    print(f"abstained but answer text is not the canned refusal ({len(x['abstained_noncanned'])}):")
    for a in x["abstained_noncanned"]:
        print(f"  {a['id']}: {a['answer']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
