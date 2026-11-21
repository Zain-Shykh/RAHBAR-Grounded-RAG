#!/usr/bin/env python3
"""Summarise the trace log over a time window (R3-D3-1, R3-D3-2).

    python scripts/trace_report.py --dir traces/samples --since 24h [--out traces/report.txt]

Top-1 similarity distribution, abstention rate, cache hit rate, p50 and p95 latency per stage, injection flags.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from pathlib import Path


def load(directory: str, since_s: float | None) -> list[dict]:
    cutoff = time.time() - since_s if since_s else 0
    out = []
    for f in sorted(Path(directory).glob("*.jsonl")):
        for ln in f.read_text(encoding="utf-8").splitlines():
            if not ln.startswith("{"):
                continue
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if r.get("type") != "trace":
                continue
            ts = time.mktime(time.strptime(r["ts"], "%Y-%m-%dT%H:%M:%SZ")) - time.timezone
            if ts >= cutoff:
                out.append(r)
    return out


def pct(values: list[float], p: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    return s[max(0, math.ceil(p * len(s)) - 1)]


def parse_window(s: str | None) -> float | None:
    if not s:
        return None
    m = re.fullmatch(r"(\d+)([smhd])", s)
    if not m:
        raise SystemExit("--since looks like 30m, 24h, 7d")
    return int(m.group(1)) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[m.group(2)]


def summarise(rows: list[dict]) -> dict:
    n = len(rows)
    top1 = [r["retrieved"][0]["score"] for r in rows if r["retrieved"]]
    buckets = {f"{lo:.1f}-{lo + 0.1:.1f}": 0 for lo in [x / 10 for x in range(2, 10)]}
    for s in top1:
        lo = min(max(math.floor(s * 10) / 10, 0.2), 0.9)
        buckets[f"{lo:.1f}-{lo + 0.1:.1f}"] += 1
    looked = [r for r in rows if r["cache"] in ("hit", "miss")]
    stages = {}
    for st in ("scope", "embed", "cache", "retrieve", "guardrails", "generate", "total"):
        v = [r["latency_ms"].get(st, 0.0) for r in rows]
        stages[st] = {"p50": pct(v, 0.5), "p95": pct(v, 0.95)}
    return {"queries": n, "top1_similarity": {"min": min(top1, default=None), "p25": pct(top1, .25), "median": pct(top1, .5),
            "p75": pct(top1, .75), "max": max(top1, default=None), "histogram": buckets},
            "abstention_rate": sum(r["response"]["outcome"] == "abstained" for r in rows) / n if n else None,
            "fallback_rate": sum(r["response"]["outcome"] == "fallback" for r in rows) / n if n else None,
            "cache_hit_rate": (sum(r["cache"] == "hit" for r in looked) / len(looked)) if looked else None,
            "cache_lookups": len(looked), "latency_ms": stages,
            "injection_flags": sum(1 for r in rows for g in r["guardrails"] if g["rail"] == "injection_scan"),
            "collections": sorted({r["collection"]["name"] + "@" + str(r["collection"]["index_id"]) for r in rows})}


def text(s: dict) -> str:
    f = lambda x: "n/a" if x is None else f"{x:.3f}"  # noqa: E731
    o = [f"queries: {s['queries']}", f"collections seen: {', '.join(s['collections'])}", "",
         "top-1 similarity: " + ", ".join(f"{k} {f(v)}" for k, v in s["top1_similarity"].items() if k != "histogram"),
         "histogram: " + ", ".join(f"{k}:{v}" for k, v in s["top1_similarity"]["histogram"].items()),
         f"abstention rate: {f(s['abstention_rate'])}   fallback rate: {f(s['fallback_rate'])}",
         f"cache hit rate: {f(s['cache_hit_rate'])} over {s['cache_lookups']} lookups",
         f"injection attempts flagged: {s['injection_flags']}", "", "latency ms per stage (p50 / p95):"]
    o += [f"  {k:<11} {f(v['p50'])} / {f(v['p95'])}" for k, v in s["latency_ms"].items()]
    return "\n".join(o)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="traces/samples")
    ap.add_argument("--since")
    ap.add_argument("--out")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    s = summarise(load(a.dir, parse_window(a.since)))
    out = json.dumps(s, indent=2) if a.json else text(s)
    print(out)
    if a.out:
        Path(a.out).write_text(out + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
