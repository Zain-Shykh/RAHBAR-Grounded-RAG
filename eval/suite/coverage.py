"""Coverage checking (R3-E1 to E4): are the golden questions still representative of live queries?

    python -m eval.suite.coverage --live eval/live_queries.jsonl --golden eval/golden.jsonl [--out result.json]

For each live query: the most similar golden question (cosine of query embeddings). Reports the share at or above
the threshold, lists the uncovered queries grouped by their expected topic, and exits 1 when the share is below the
target (the paper's example flags a gap under 85 percent). Threshold and target come from eval/coverage.yaml.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import yaml

from .golden import load
from .module_level import Embedder, cos

HERE = Path(__file__).resolve().parents[1]


def coverage(live: list[dict], golden_rows: list[dict], vecs: dict[str, list[float]], threshold: float) -> dict:
    gq = [(g["id"], g["question"]) for g in golden_rows]
    per = []
    for q in live:
        best = max(((cos(vecs[q["query"]], vecs[g[1]]), g[0]) for g in gq), key=lambda x: x[0])
        per.append({"id": q["id"], "query": q["query"], "topic": q["expected_topic"], "in_domain": q["in_domain"],
                    "best_cosine": round(best[0], 4), "nearest_golden": best[1], "covered": best[0] >= threshold})
    covered = [p for p in per if p["covered"]]
    uncovered = [p for p in per if not p["covered"]]
    topics: dict[str, list[str]] = {}
    for p in uncovered:
        topics.setdefault(p["topic"], []).append(p["id"])
    dom = [p for p in per if p["in_domain"]]
    return {"live_queries": len(per), "covered": len(covered), "share": len(covered) / len(per) if per else 0.0,
            "in_domain_share": (sum(p["covered"] for p in dom) / len(dom)) if dom else None,
            "threshold": threshold, "uncovered": uncovered, "uncovered_topics": topics, "per_query": per}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", default=str(HERE / "live_queries.jsonl"))
    ap.add_argument("--golden", default=str(HERE / "golden.jsonl"))
    ap.add_argument("--config", default=str(HERE / "coverage.yaml"))
    ap.add_argument("--out")
    a = ap.parse_args()
    cfg = yaml.safe_load(Path(a.config).read_text())
    live = [json.loads(ln) for ln in Path(a.live).read_text().splitlines() if ln.strip()]
    g = load(a.golden)
    e = Embedder()
    texts = sorted({q["query"] for q in live} | {r["question"] for r in g})
    vecs: dict[str, list[float]] = {}
    for i in range(0, len(texts), 32):
        batch = texts[i:i + 32]
        for t, v in zip(batch, e.embed(["search_query: " + x for x in batch]), strict=True):
            vecs[t] = v
    res = coverage(live, g, vecs, cfg["threshold"])
    res.update(target=cfg["target"], golden_questions=len(g), embedding=e.version(),
               created=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    print(f"live queries {res['live_queries']}, golden questions {len(g)}, threshold {res['threshold']}, target {res['target']}")
    print(f"covered {res['covered']} of {res['live_queries']}: share {res['share']:.3f}  (in-domain share {res['in_domain_share'] if res['in_domain_share'] is None else format(res['in_domain_share'], '.3f')})")
    print("uncovered queries by topic:")
    for topic, ids in sorted(res["uncovered_topics"].items()):
        print(f"  {topic}: {', '.join(ids)}")
    for p in res["uncovered"]:
        print(f"    {p['id']} {p['best_cosine']:.3f} (nearest {p['nearest_golden']})  {p['query']}")
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=2) + "\n")
    ok = res["share"] >= cfg["target"]
    print("COVERAGE " + ("OK" if ok else "BELOW TARGET"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
