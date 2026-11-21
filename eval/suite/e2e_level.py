"""End-to-end level: answers (R3-B-6, paper Table 1 row 3).

Faithfulness is the deterministic support-overlap score (D-115: no LLM judge): the share of an answer's content
tokens found in the passages it cites. A response counts as supported at or above SUPPORT_THRESHOLD.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .client import Api
from .metrics import mean, percentile, support_overlap

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_eval import _citation_counts, _norm  # noqa: E402

SUPPORT_THRESHOLD = 0.6


def run(api: Api, rows: list[dict], threshold: float = SUPPORT_THRESHOLD) -> dict:
    per = []
    for q in rows:
        resp, secs = api.ask(q["question"])
        meta = resp.get("_meta") or {}
        answered = bool(resp.get("answered_from_context"))
        overlap = None
        if answered:
            passages = {(p["source"], p["section"]): p["text"] for p in api.retrieve(q["question"])["retrieved"]}
            context = " ".join(passages.get((c["source"], c["section"]), "") for c in resp.get("citations", []))
            overlap = support_overlap(resp["answer"], context)
        v, t = _citation_counts(resp)
        expect = q.get("expect")
        per.append({"id": q["id"], "kind": q["kind"], "batch": q.get("batch", "A"), "hard": q.get("hard", False),
                    "trace_id": resp.get("request_id"), "outcome": meta.get("outcome"), "answered": answered,
                    "answer": resp["answer"], "citations": resp.get("citations", []), "overlap": overlap,
                    "citations_valid": v, "citations_total": t, "seconds": round(secs, 2),
                    "expect_hit": (_norm(expect) in _norm(resp["answer"])) if (expect and answered) else None})
    un = [p for p in per if p["kind"] == "unanswerable"]
    ans = [p for p in per if p["kind"] == "answerable"]
    answered = [p for p in per if p["answered"]]
    secs = [p["seconds"] for p in per]
    return {
        "n": len(per),
        "abstention_correctness": (sum(not p["answered"] for p in un) / len(un)) if un else None,
        "abstention_n": len(un), "abstention_failed": [p["id"] for p in un if p["answered"]],
        "false_abstention_rate": (sum(not p["answered"] for p in ans) / len(ans)) if ans else None,
        "citation_validity": (sum(p["citations_valid"] for p in per) / max(1, sum(p["citations_total"] for p in per))),
        "citations_total": sum(p["citations_total"] for p in per),
        "faithfulness_overlap_mean": mean([p["overlap"] for p in answered]),
        "faithfulness_supported_rate": (sum(p["overlap"] >= threshold for p in answered) / len(answered)) if answered else None,
        "support_threshold": threshold, "answered_n": len(answered),
        "expect_hit_rate": mean([1.0 if p["expect_hit"] else 0.0 for p in per if p["expect_hit"] is not None]),
        "fallback_rate": sum(p["outcome"] == "fallback" for p in per) / len(per),
        "latency_p50_s": percentile(secs, 0.5), "latency_p95_s": percentile(secs, 0.95),
        "per_question": per,
    }
