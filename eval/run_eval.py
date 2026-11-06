#!/usr/bin/env python3
"""Score a running RAHBAR against a golden set, and gate CI on the result (section 5).

    python eval/run_eval.py --api http://<ingress>                 # your corpus
    python eval/run_eval.py --api ... --golden eval/fixtures/golden.fixture.yaml
    python eval/run_eval.py --api ... --update-baseline            # after a deliberate improvement

Exit code 0 when every gate passes, 1 when any fails or a call to the API fails. CI relies on
that exit code. Matching, metrics and the gate follow architecture 5.13.2 and 5.13.3.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import unicodedata
from pathlib import Path

import httpx
import yaml

HERE = Path(__file__).resolve().parent

# The gate from section 5.4. Change these only with a reason written in docs/PIPELINE.md.
MAX_RECALL5_DROP = 0.05        # recall@5 may fall at most 5 points below the baseline
MIN_CITATION_VALIDITY = 0.95   # at least 95% of citations must match retrieved passages
REQUIRED_ABSTENTION = 1.0      # every must-abstain question must be declined


def load_golden(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    questions = data.get("questions") or []
    if not questions:
        sys.exit(f"no questions in {path}")
    return questions


def ask(client: httpx.Client, api: str, question: str) -> dict:
    """POST one question and return the AskResponse as a dict (see api/app/schemas.py).
    The X-Outcome and X-Cache headers go under "_meta"; the API JSON is left as it is."""
    response = client.post(f"{api.rstrip('/')}/api/ask", json={"question": question})
    response.raise_for_status()
    data = response.json()
    data["_meta"] = {"outcome": response.headers.get("X-Outcome"),
                     "cache": response.headers.get("X-Cache")}
    return data


_DASHES = dict.fromkeys(map(ord, "‐‑‒–—―−"), "-")


def _norm(text: str) -> str:
    """NFKC, dash variants to "-", lower case, whitespace collapsed (AD-22, D-046, DEV-002)."""
    text = unicodedata.normalize("NFKC", text).translate(_DASHES)
    return re.sub(r"\s+", " ", text).strip().lower()


def section_matches(golden: str, retrieved: str) -> bool:
    """Equal after normalising, or the retrieved section starts with the golden one followed
    by a space, "." or ":" (so 1.21 matches "1.21 Attendance" but 1.2 does not match 1.21)."""
    g, r = _norm(golden), _norm(retrieved)
    return r == g or (r.startswith(g) and r[len(g)] in " .:")


def recall_at_k(relevant: list[dict], retrieved: list[dict], k: int) -> float | None:
    """Fraction of the relevant (source, section) pairs found in the top k retrieved.
    Return None when the question has no relevant passages (must-abstain questions)."""
    if not relevant:
        return None
    top = retrieved[:k]
    hits = sum(
        any(g["source"] == r["source"] and section_matches(g["section"], r["section"]) for r in top)
        for g in relevant
    )
    return hits / len(relevant)


def _citation_counts(response: dict) -> tuple[int, int]:
    """(valid, total) citations; valid = same source and section as some retrieved passage (5.8)."""
    seen = {(r["source"], r["section"]) for r in response.get("retrieved") or []}
    cites = response.get("citations") or []
    return sum((c["source"], c["section"]) in seen for c in cites), len(cites)


def citation_validity(response: dict) -> float | None:
    """Fraction of the response's citations that match a passage in response['retrieved'].
    Return None when there are no citations."""
    valid, total = _citation_counts(response)
    return valid / total if total else None


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _percentile(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p * len(ordered)) - 1)]


def summarise(rows: list[dict]) -> dict:
    """Overall recall@3 and recall@5, recall by question type, citation validity, abstention
    correctness, fallback rate and latency. This dict becomes results.json."""
    per_question = []
    by_type: dict[str, dict[str, list[float]]] = {}
    valid = total = must = leaked = declined_by_fallback = fallbacks = 0
    leaked_ids: list[str] = []
    for row in rows:
        resp = row["response"]
        meta = resp.get("_meta") or {}
        outcome = meta.get("outcome")
        retrieved = resp.get("retrieved") or []
        r3 = recall_at_k(row["relevant"], retrieved, 3)
        r5 = recall_at_k(row["relevant"], retrieved, 5)
        if r3 is not None and r5 is not None:
            slot = by_type.setdefault(row["type"], {"r3": [], "r5": []})
            slot["r3"].append(r3)
            slot["r5"].append(r5)
        v, t = _citation_counts(resp)
        valid, total = valid + v, total + t
        fallbacks += outcome == "fallback"
        if row["must_abstain"]:
            must += 1
            if resp.get("answered_from_context") is False:
                declined_by_fallback += outcome == "fallback"
            else:
                leaked += 1
                leaked_ids.append(row["id"])
        per_question.append({"id": row["id"], "type": row["type"], "recall_at_3": r3,
                             "recall_at_5": r5, "outcome": outcome, "cache": meta.get("cache"),
                             "seconds": row["seconds"]})
    seconds = [row["seconds"] for row in rows]
    return {
        "recall_at_3": _mean([q["recall_at_3"] for q in per_question if q["recall_at_3"] is not None]),
        "recall_at_5": _mean([q["recall_at_5"] for q in per_question if q["recall_at_5"] is not None]),
        "by_type": {t: {"recall_at_3": _mean(v["r3"]), "recall_at_5": _mean(v["r5"]), "n": len(v["r5"])}
                    for t, v in by_type.items()},
        "citation_validity": valid / total if total else None,
        "citations_total": total,
        "citations_valid": valid,
        "abstention_correctness": (must - leaked) / must if must else None,
        "must_abstain_total": must,
        "must_abstain_failed": leaked_ids,
        "must_abstain_fallback": declined_by_fallback,
        "fallback_rate": fallbacks / len(rows) if rows else 0.0,
        "latency_p50": _percentile(seconds, 0.50),
        "latency_p95": _percentile(seconds, 0.95),
        "per_question": per_question,
    }


def golden_label(path: Path) -> str:
    """Golden path as stored in results: relative to the repo root when inside it."""
    p = Path(path).resolve()
    try:
        return p.relative_to(HERE.parent).as_posix()
    except ValueError:
        return p.as_posix()


def gate(results: dict, baseline: dict | None) -> list[str]:
    """Return one message per failed gate (architecture 5.13.3); an empty list means pass."""
    messages = []
    now = results.get("recall_at_5")
    before = (baseline or {}).get("recall_at_5")
    if now is not None and before is not None and before - now > MAX_RECALL5_DROP + 1e-9:
        messages.append(f"recall@5 fell from {before:.3f} to {now:.3f}, more than "
                        f"{MAX_RECALL5_DROP * 100:.0f} points below the baseline")
    abstention = results.get("abstention_correctness")
    if abstention is not None and abstention < REQUIRED_ABSTENTION:
        ids = ", ".join(results.get("must_abstain_failed") or [])
        messages.append(f"must-abstain answered from context: {ids} (abstention {abstention:.2f})")
    citations = results.get("citation_validity")
    if citations is not None and citations < MIN_CITATION_VALIDITY:
        messages.append(f"citation validity {citations:.3f} is below {MIN_CITATION_VALIDITY}")
    return messages


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate RAHBAR against a golden set.")
    parser.add_argument("--api", required=True, help="base URL, e.g. http://192.168.49.2")
    parser.add_argument("--host", help="Host header, when your Ingress rule names a host")
    parser.add_argument("--golden", type=Path, default=HERE / "golden.yaml")
    parser.add_argument("--baseline", type=Path, default=HERE / "baseline.json")
    parser.add_argument("--out", type=Path, default=HERE / "results.json")
    parser.add_argument("--update-baseline", action="store_true",
                        help="write these results as the new baseline")
    args = parser.parse_args()

    questions = load_golden(args.golden)
    rows = []
    headers = {"Host": args.host} if args.host else {}
    with httpx.Client(timeout=300.0, headers=headers) as client:
        for q in questions:
            started = time.perf_counter()
            try:
                response = ask(client, args.api, q["question"])
            except (httpx.HTTPError, ValueError, TypeError) as exc:  # D-047: never score a half run
                print(f"ERROR: question {q['id']}: {exc!r}. Run aborted, nothing written.")
                return 1
            rows.append({
                "id": q["id"], "type": q.get("type", "ordinary"),
                "must_abstain": bool(q.get("must_abstain", False)),
                "relevant": q.get("relevant") or [],
                "expect": q.get("expect"),
                "response": response,
                "seconds": round(time.perf_counter() - started, 2),
            })
            print(f"  {q['id']:<5} {rows[-1]['seconds']:>6.2f}s  {q['question'][:60]}")

    results = summarise(rows)
    try:
        baseline = json.loads(args.baseline.read_text()) if args.baseline.exists() else None
        if baseline is not None:
            recall = baseline.get("recall_at_5") if isinstance(baseline, dict) else "-"
            if recall is not None and (isinstance(recall, bool) or not isinstance(recall, (int, float))
                                       or not math.isfinite(recall)):
                raise ValueError("expected a JSON object with a finite numeric or null recall_at_5")
    except (OSError, ValueError) as exc:
        print(f"ERROR: baseline {args.baseline}: {exc}. Nothing written.")
        return 1
    failures = gate(results, baseline)

    results["golden"] = golden_label(args.golden)
    results["questions"] = len(rows)
    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nresults written to {args.out}")
    # D-048: a recall drop may be saved as a deliberate choice; a leak or bad citations never.
    blocking = [m for m in failures if not m.startswith("recall@5")]
    if args.update_baseline and blocking:
        print("baseline NOT updated: abstention or citation gate failed")
    elif args.update_baseline:
        args.baseline.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"baseline updated: {args.baseline}")

    if failures:
        print("\nGATE FAILED")
        for message in failures:
            print(f"  - {message}")
        return 1
    print("\ngate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
