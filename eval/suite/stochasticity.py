"""Two runs, one difference per metric (R3-B-8). `python -m eval.suite.stochasticity A.json B.json`."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

KEYS = [("component.clean", ("recall_at_3", "recall_at_5", "mrr", "ndcg_at_5")),
        ("component.noisy", ("recall_at_3", "recall_at_5", "mrr", "ndcg_at_5")),
        ("e2e", ("abstention_correctness", "false_abstention_rate", "citation_validity", "faithfulness_overlap_mean",
                 "faithfulness_supported_rate", "expect_hit_rate", "fallback_rate", "latency_p50_s", "latency_p95_s")),
        ("module", ("paraphrase_mean", "unrelated_mean", "gap", "determinism_max_abs_diff", "ms_per_chunk_median"))]


def get(res: dict, path: str) -> dict:
    d = res
    for part in path.split("."):
        d = d[part]
    return d


def compare(a: dict, b: dict) -> dict:
    rows = {}
    for path, keys in KEYS:
        for k in keys:
            x, y = get(a, path).get(k), get(b, path).get(k)
            rows[f"{path}.{k}"] = {"run1": x, "run2": y, "abs_diff": None if x is None or y is None else abs(x - y)}
    qa = {p["id"]: p for p in a["e2e"]["per_question"]}
    qb = {p["id"]: p for p in b["e2e"]["per_question"]}
    differ = [i for i in qa if i in qb and qa[i]["answer"] != qb[i]["answer"]]
    outcome = [i for i in qa if i in qb and (qa[i]["answered"], [c["section"] for c in qa[i]["citations"]]) !=
               (qb[i]["answered"], [c["section"] for c in qb[i]["citations"]])]
    return {"metrics": rows, "answers_differing_text": differ, "answers_differing_outcome_or_citations": outcome,
            "questions": len(qa)}


def main() -> int:
    a, b = (json.loads(Path(p).read_text()) for p in sys.argv[1:3])
    out = compare(a, b)
    out["runs"] = sys.argv[1:3]
    dest = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(sys.argv[1]).parent / \
        f"stochasticity-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
    dest.write_text(json.dumps(out, indent=2) + "\n")
    for k, v in out["metrics"].items():
        print(f"{k:<48} {v['run1']!s:<22} {v['run2']!s:<22} diff {v['abs_diff']}")
    print(f"answers with different text: {len(out['answers_differing_text'])} of {out['questions']}; "
          f"different outcome or citations: {len(out['answers_differing_outcome_or_citations'])}")
    print("wrote", dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
