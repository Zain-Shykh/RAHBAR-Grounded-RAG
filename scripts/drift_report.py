#!/usr/bin/env python3
"""E3 data drift (R3-E3-1, R10-AC5): Batch A suite versus Batch A+B suite, same questions.

    python scripts/drift_report.py eval/results/suite-<A>.json eval/results/suite-<A+B>.json [--out eval/results]

Writes eval/results/drift-<utc ts>.json and prints the markdown tables. Two views:
 1. `eval.suite.compare.table` on the two files as they are (the second also has the 23 Batch B questions);
 2. the same metrics recomputed from the per-question rows restricted to the ids present in the first file
    (like for like). The recomputation is checked against the first file's own reported numbers first.
Causes are stated only when a committed file shows the mechanism; the rest is marked `not shown by the files`.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval.suite.compare import table  # noqa: E402

TH = 0.6


def restrict(res: dict, ids: set[str]) -> dict:
    comp = [q for q in res["component"]["clean"]["per_question"] if q["id"] in ids]
    e2e = [q for q in res["e2e"]["per_question"] if q["id"] in ids]
    un = [q for q in e2e if q["kind"] == "unanswerable"]
    an = [q for q in e2e if q["kind"] == "answerable"]
    ans = [q for q in e2e if q["answered"]]
    avg = lambda xs: sum(xs) / len(xs)  # noqa: E731
    return {
        "recall_at_5": avg([q["recall_at_5"] for q in comp]), "mrr": avg([q["mrr"] for q in comp]),
        "ndcg_at_5": avg([q["ndcg_at_5"] for q in comp]), "answerable_n": len(comp),
        "abstention_correctness": sum(not q["answered"] for q in un) / len(un),
        "false_abstention_rate": sum(not q["answered"] for q in an) / len(an),
        "citation_validity": sum(q["citations_valid"] for q in e2e) / max(1, sum(q["citations_total"] for q in e2e)),
        "faithfulness_supported_rate": sum(q["overlap"] >= TH for q in ans) / len(ans),
        "faithfulness_overlap_mean": avg([q["overlap"] for q in ans]), "answered_n": len(ans),
        "fallback_rate": sum(q["outcome"] == "fallback" for q in e2e) / len(e2e),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("a"), ap.add_argument("b")
    ap.add_argument("--out", default="eval/results")
    a = ap.parse_args()
    A, B = (json.loads(Path(p).read_text()) for p in (a.a, a.b))
    ids = {q["id"] for q in A["e2e"]["per_question"]}
    ra, rb = restrict(A, ids), restrict(B, ids)
    rep = {"recall_at_5": A["component"]["clean"]["recall_at_5"], "mrr": A["component"]["clean"]["mrr"],
           "abstention_correctness": A["e2e"]["abstention_correctness"],
           "faithfulness_supported_rate": A["e2e"]["faithfulness_supported_rate"]}
    for k, v in rep.items():   # self-check: the recomputation reproduces the file's own numbers
        assert abs(ra[k] - v) < 1e-9, (k, ra[k], v)
    qa = {q["id"]: q for q in A["e2e"]["per_question"]}
    qb = {q["id"]: q for q in B["e2e"]["per_question"]}
    ca = {q["id"]: q for q in A["component"]["clean"]["per_question"]}
    cb = {q["id"]: q for q in B["component"]["clean"]["per_question"]}
    changed = []
    for i in sorted(ids):
        x, y = qa[i], qb[i]
        retr = (ca.get(i, {}).get("recall_at_5"), cb.get(i, {}).get("recall_at_5"))
        if x["outcome"] != y["outcome"] or retr[0] != retr[1]:
            changed.append({"id": i, "kind": x["kind"], "outcome_before": x["outcome"], "outcome_after": y["outcome"],
                            "answer_before": x["answer"], "answer_after": y["answer"],
                            "cited_before": [c["source"] for c in x["citations"]],
                            "cited_after": [c["source"] for c in y["citations"]],
                            "recall_at_5_before": retr[0], "recall_at_5_after": retr[1]})
    same_outcome_other_text = [i for i in sorted(ids) if qa[i]["outcome"] == qb[i]["outcome"] and qa[i]["answer"] != qb[i]["answer"]]
    new = [q for q in B["e2e"]["per_question"] if q["id"] not in ids]
    by_b = B["component"]["clean"]["by_batch"].get("B")
    drift = {
        "baseline": a.a, "after": a.b, "index_before": A["meta"]["index_id"], "index_after": B["meta"]["index_id"],
        "questions_like_for_like": len(ids), "questions_after_total": B["e2e"]["n"], "questions_batch_b": len(new),
        "like_for_like": {"before": ra, "after": rb, "change": {k: rb[k] - ra[k] for k in ra if isinstance(ra[k], float)}},
        "retrieval_changed": [c["id"] for c in changed if c["recall_at_5_before"] != c["recall_at_5_after"]],
        "outcome_changed": changed,
        "same_outcome_different_text": same_outcome_other_text,
        "batch_b": {"retrieval": by_b, "answered": sum(q["answered"] for q in new), "abstained": sum(not q["answered"] for q in new),
                    "version_question_g33": {"answer": qb["g33"]["answer"], "cited": [c["source"] for c in qb["g33"]["citations"]],
                                            "recall_at_5": cb["g33"]["recall_at_5"]},
                    "injection_questions": {i: {"outcome": qb[i]["outcome"], "answer": qb[i]["answer"],
                                                "recall_at_5": cb[i]["recall_at_5"], "top1_score": cb[i]["top1_score"]} for i in ("g31", "g34")},
                    "new_questions_not_in_baseline": [q["id"] for q in new]},
        "causes": {
            "q07_g22_fee_refund": "The refund answer lived only in fee-structure-page.html. Batch B's b10-fee-structure-amendment-2027.md "
                                  "supersedes that page (docs/evidence/a3/a2-batch-b-ingest.txt: superseded 1, flipped 1), retrieval filters superseded "
                                  "chunks (trace scope.where superseded=false), so the golden source is no longer retrieved (recall@5 1 to 0) and the "
                                  "amendment has no refund clause: the system abstains. Correct behaviour of the version rule; the golden labels for "
                                  "q07 and g22 are out of date and need a human decision (eval/HUMAN_TODO.md).",
            "q06": "Retrieval is identical (same recall, same top-1 score within 1e-7); only the generation changed (answer fell back after the "
                   "citation check). Not caused by Batch B: generation variance. The seeded two-run test changed 1 of 27 answer texts "
                   "(eval/results/stochasticity-20261121T003255Z.json).",
            "g21": "Retrieval and outcome identical; the answer was No in both runs, the citation list differs: generation variance.",
            "g32": "b12-sports-facilities-2026.md (the gymnasium hours) was deleted from the inbox by the A2 delete test before this "
                   "index was built (docs/evidence/a3/a2-delete-no-orphans.txt: chunks left under b12 = 0, index 1006 chunks, 14 documents); "
                   "its abstention is the correct answer for an index without the document, not a drift effect of adding Batch B.",
            "injected_document": "g31: b11 is retrieved (recall@5 1.0, top-1 0.8616) and the answer abstains; the rail dropped the chunk "
                                 "b11-examination-guidelines-2026-p001-c002 (live trace, docs/evidence/a3/e3-injection-rail-live.txt), which also holds "
                                 "the legitimate rule. g34: b11 not in the top 5 (recall@5 0.0), rail not shown to be involved.",
        },
    }
    out = Path(a.out) / f"drift-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
    out.write_text(json.dumps(drift, indent=2) + "\n")
    print(table(A, B))
    print("\nlike for like on the", len(ids), "questions of the baseline:")
    for k in ra:
        print(f"  {k}: {ra[k]:.4f} -> {rb[k]:.4f}")
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
