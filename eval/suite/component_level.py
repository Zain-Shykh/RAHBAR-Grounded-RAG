"""Component level: retrieval (R3-B-4, R3-B-5, paper Table 1 row 2).

Uses POST /api/retrieve (the live retriever, no model call). recall@3, recall@5, MRR, nDCG@5 over the answerable
questions, clean and with seeded typos in the query.
"""

from __future__ import annotations

from .client import Api
from .metrics import add_typos, mean, ndcg_at_k, percentile, recall_at_k, reciprocal_rank


def score(rows: list[dict], retrieved_by_id: dict[str, list[dict]]) -> dict:
    per = []
    for q in rows:
        if q["kind"] != "answerable":
            continue
        got = retrieved_by_id[q["id"]]
        per.append({"id": q["id"], "tags": q.get("tags", []), "hard": q.get("hard", False), "batch": q.get("batch", "A"),
                    "recall_at_3": recall_at_k(q["relevant"], got, 3), "recall_at_5": recall_at_k(q["relevant"], got, 5),
                    "mrr": reciprocal_rank(q["relevant"], got, 5), "ndcg_at_5": ndcg_at_k(q["relevant"], got, 5),
                    "top1_score": got[0]["score"] if got else None})
    def agg(sel: list[dict]) -> dict:
        return {"n": len(sel), **{m: mean([p[m] for p in sel]) for m in ("recall_at_3", "recall_at_5", "mrr", "ndcg_at_5")}}
    out = agg(per)
    out["hard"] = agg([p for p in per if p["hard"]])
    out["by_batch"] = {b: agg([p for p in per if p["batch"] == b]) for b in sorted({p["batch"] for p in per})}
    out["per_question"] = per
    return out


def run(api: Api, rows: list[dict], seed: int = 1234) -> dict:
    clean: dict[str, list[dict]] = {}
    noisy: dict[str, list[dict]] = {}
    ms: list[float] = []
    queries: dict[str, str] = {}
    for q in rows:
        r = api.retrieve(q["question"])
        clean[q["id"]] = r["retrieved"]
        ms.append(r["ms_retrieve"])
        noisy_q = add_typos(q["question"], seed + sum(map(ord, q["id"])))
        queries[q["id"]] = noisy_q
        noisy[q["id"]] = api.retrieve(noisy_q)["retrieved"]
    c, n = score(rows, clean), score(rows, noisy)
    metrics = ("recall_at_3", "recall_at_5", "mrr", "ndcg_at_5")
    delta = {m: {"clean": c[m], "noisy": n[m], "abs": (n[m] or 0) - (c[m] or 0),
                 "rel": ((n[m] or 0) - (c[m] or 0)) / c[m] if c[m] else None} for m in metrics}
    return {"clean": c, "noisy": n, "noise_delta": delta, "noise_seed": seed, "noise_examples":
            {k: queries[k] for k in list(queries)[:3]},
            "retrieval_ms_median": percentile(ms, 0.5), "retrieval_ms_p95": percentile(ms, 0.95),
            "chunk_texts": sorted({p["text"] for v in clean.values() for p in v})[:150]}
