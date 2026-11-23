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
CANNED = ("The documents in the corpus do not cover this question.", "I could not produce a verified answer")


def cites_gold(citations: list[dict], relevant: list[dict]) -> bool:
    """True if some citation names a gold source and a section that is the gold section or starts with / is contained in it
    (the API truncates long headings, so equality would miss real hits)."""
    for c in citations:
        for r in relevant:
            a, b = str(c.get("section", "")), str(r.get("section", ""))
            if c.get("source") == r.get("source") and (a == b or a.startswith(b) or b.startswith(a)):
                return True
    return False


def extra_metrics(per: list[dict], rows: list[dict]) -> dict:
    """Checks that the three headline metrics do not make (limits listed in the report, section 3 B):
    - gold_citation_rate: of the answered answerable questions, the share whose citations include a gold passage
      (citation_validity only says the citation was retrieved, not that it is the right place);
    - abstained_noncanned: abstained responses whose text is not the canned refusal, so the flag and the text disagree
      or the model made a claim while flagging no evidence (the abstention rate counts them as abstentions)."""
    gold = {r["id"]: r.get("relevant") or [] for r in rows}
    ans = [p for p in per if p["kind"] == "answerable" and p["answered"] and gold.get(p["id"])]
    hit = [p["id"] for p in ans if cites_gold(p["citations"], gold[p["id"]])]
    return {"gold_citation_rate": (len(hit) / len(ans)) if ans else None, "gold_citation_n": len(ans),
            "gold_citation_misses": [p["id"] for p in ans if p["id"] not in hit],
            "abstained_noncanned": [{"id": p["id"], "answer": p["answer"][:120]} for p in per
                                    if not p["answered"] and not p["answer"].startswith(CANNED)]}


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
        **extra_metrics(per, rows),
        "per_question": per,
    }
