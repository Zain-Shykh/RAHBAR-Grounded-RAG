"""Baseline versus candidate over all three levels (R3-C1-2). `python -m eval.suite.compare base.json cand.json` (or two run labels)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .gate import dig

ROWS = [
    ("module", "module.paraphrase_mean", "paraphrase mean cosine"), ("module", "module.unrelated_mean", "unrelated mean cosine"),
    ("module", "module.gap", "gap"), ("module", "module.ms_per_chunk_median", "embed ms per chunk (median)"),
    ("component", "component.clean.recall_at_3", "recall@3"), ("component", "component.clean.recall_at_5", "recall@5"),
    ("component", "component.clean.mrr", "MRR"), ("component", "component.clean.ndcg_at_5", "nDCG@5"),
    ("component", "component.noisy.recall_at_5", "recall@5 with typos"), ("component", "component.noisy.mrr", "MRR with typos"),
    ("component", "component.retrieval_ms_p95", "retrieval ms p95"),
    ("e2e", "e2e.faithfulness_supported_rate", "faithfulness (share supported)"),
    ("e2e", "e2e.faithfulness_overlap_mean", "faithfulness (overlap mean)"),
    ("e2e", "e2e.abstention_correctness", "abstention correctness"), ("e2e", "e2e.false_abstention_rate", "false abstention rate"),
    ("e2e", "e2e.citation_validity", "citation validity"), ("e2e", "e2e.expect_hit_rate", "expected-text hit rate"),
    ("e2e", "e2e.latency_p50_s", "latency p50 s"), ("e2e", "e2e.latency_p95_s", "latency p95 s"),
]


def table(base: dict, cand: dict) -> str:
    f = lambda x: "n/a" if x is None else f"{x:.4f}"  # noqa: E731
    o = [f"| level | metric | baseline ({base['meta']['label']}) | candidate ({cand['meta']['label']}) | change |",
         "| --- | --- | --- | --- | --- |"]
    for level, path, label in ROWS:
        b, c = dig(base, path), dig(cand, path)
        d = "n/a" if b is None or c is None else f"{c - b:+.4f}"
        o.append(f"| {level} | {label} | {f(b)} | {f(c)} | {d} |")
    return "\n".join(o)


def resolve(arg: str) -> Path:
    """A result file, or a run label (the newest `eval/results/suite-*-<label>.json`)."""
    if Path(arg).is_file():
        return Path(arg)
    found = sorted(Path(__file__).resolve().parents[1].joinpath("results").glob(f"suite-*-{arg}.json"))
    if not found:
        raise SystemExit(f"no result file or run label {arg!r}")
    return found[-1]


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: python -m eval.suite.compare <baseline.json|label> <candidate.json|label>")
    b, c = (json.loads(resolve(p).read_text()) for p in sys.argv[1:3])
    print(table(b, c))
