#!/usr/bin/env python3
"""Retrieval without the LLM, against the live index (phase 8). A developer tool, not part of CI.

    python eval/retrieval_only.py ask "What is the deadline to withdraw from a course?"
    python eval/retrieval_only.py recall [--golden eval/golden.yaml] [--json out.json]
    python eval/retrieval_only.py loop --seconds 120     # query continuously, count errors

Reads the same environment as the API: CHROMA_HOST, CHROMA_PORT, OLLAMA_URL, EMBED_MODEL, TOP_K.
Recall is scored with run_eval.summarise, exactly as the full evaluation will be.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "api"))

import run_eval  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.retrieval.chroma import ChromaRetriever  # noqa: E402
from app.services.scope import scope  # noqa: E402


def retrieve(r: ChromaRetriever, question: str, k: int) -> tuple[str, list]:
    sc = scope(question, r.state.get().doc_versions)
    return sc.key, r.retrieve(question, k, where=sc.where)


def cmd_ask(r: ChromaRetriever, a: argparse.Namespace) -> int:
    key, passages = retrieve(r, a.question, a.k)
    print(f"scope: {key}")
    for p in passages:
        print(f"  {p.score:.3f}  {p.source}  [{p.section}]  p.{p.page}  {p.text[:90]!r}")
    return 0


def cmd_recall(r: ChromaRetriever, a: argparse.Namespace) -> int:
    rows = []
    for q in run_eval.load_golden(Path(a.golden)):
        t = time.perf_counter()
        key, passages = retrieve(r, q["question"], 5)
        retrieved = [{"chunk_id": p.chunk_id, "source": p.source, "section": p.section,
                      "page": p.page, "score": p.score} for p in passages]
        rows.append({"id": q["id"], "type": q.get("type", "ordinary"), "relevant": q.get("relevant") or [],
                     "must_abstain": bool(q.get("must_abstain", False)),
                     "response": {"retrieved": retrieved, "citations": [], "_meta": {}},
                     "seconds": time.perf_counter() - t, "scope": key})
    res = run_eval.summarise(rows)
    fmt = lambda v: "n/a" if v is None else f"{v:.3f}"  # noqa: E731
    print(f"recall@3 {fmt(res['recall_at_3'])}   recall@5 {fmt(res['recall_at_5'])}")
    for t, v in sorted(res["by_type"].items()):
        print(f"  {t:<10} n={v['n']:<3} recall@3 {fmt(v['recall_at_3'])}  recall@5 {fmt(v['recall_at_5'])}")
    scopes = {row["id"]: row["scope"] for row in rows}
    for q in res["per_question"]:
        if q["recall_at_5"] is not None and q["recall_at_5"] < 1:
            print(f"  miss {q['id']} ({q['type']}): recall@3 {q['recall_at_3']} recall@5 {q['recall_at_5']} scope {scopes[q['id']]}")
    # Floor calibration (5.6.3): best score per question, and best score of a passage that
    # holds the answer (a golden section match) among the top 5.
    scores = []
    for row in rows:
        got = row["response"]["retrieved"]
        hit = [p["score"] for p in got if any(
            g["source"] == p["source"] and run_eval.section_matches(g["section"], p["section"])
            for g in row["relevant"])]
        scores.append({"id": row["id"], "type": row["type"], "must_abstain": row["must_abstain"],
                       "top": max((p["score"] for p in got), default=0.0),
                       "hit": max(hit, default=None)})
    print("  scores (top = best retrieved, hit = best passage holding the answer):")
    for sc in scores:
        hit = "  -  " if sc["hit"] is None else f"{sc['hit']:.3f}"
        flag = "ABSTAIN" if sc["must_abstain"] else "       "
        print(f"    {sc['id']}  {sc['type']:<9} {flag} top {sc['top']:.3f}  hit {hit}")
    if a.json:
        Path(a.json).write_text(json.dumps({**res, "scores": scores}, indent=2), encoding="utf-8")
    return 0


def cmd_loop(r: ChromaRetriever, a: argparse.Namespace) -> int:
    questions = [q["question"] for q in run_eval.load_golden(Path(a.golden))]
    errors: collections.Counter[str] = collections.Counter()
    n = ok = 0
    ids: set[str] = set()
    end = time.monotonic() + a.seconds
    while time.monotonic() < end:
        n += 1
        try:
            retrieve(r, questions[n % len(questions)], 5)
            ok += 1
            ids.add(r.state.get().index_id)
        except Exception as exc:  # the point of the loop: nothing unexpected may escape
            errors[f"{type(exc).__name__}: {str(exc)[:100]}"] += 1
        time.sleep(a.pause)
    print(f"queries {n}, ok {ok}, errors {sum(errors.values())}, index_ids seen {sorted(ids)}")
    for msg, c in errors.items():
        print(f"  {c:>4}  {msg}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ask")
    p.add_argument("question")
    p.add_argument("-k", type=int, default=5)
    p.set_defaults(fn=cmd_ask)
    for name, fn in (("recall", cmd_recall), ("loop", cmd_loop)):
        p = sub.add_parser(name)
        p.add_argument("--golden", default=str(HERE / "golden.yaml"))
        if name == "recall":
            p.add_argument("--json")
        else:
            p.add_argument("--seconds", type=float, default=60)
            p.add_argument("--pause", type=float, default=0.2)
        p.set_defaults(fn=fn)
    a = ap.parse_args()
    return int(a.fn(ChromaRetriever(get_settings()), a))


if __name__ == "__main__":
    raise SystemExit(main())
