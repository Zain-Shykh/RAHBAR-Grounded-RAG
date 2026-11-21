#!/usr/bin/env python3
"""Print the exact context and prompt that produced an answer (R3-D2-1).

    python scripts/trace_tool.py show <trace_id> [--dir traces/samples | --kubectl deploy/api]

Finds the record in a directory of .jsonl files, or in `kubectl logs`, prints the query, the scope filter, every
retrieved chunk with score and version, the evidence blocks as the model saw them, the exact prompt messages, the
model parameters and the response, and recomputes the prompt SHA-256 (`hash OK` or `hash MISMATCH`).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def prompt_hash(messages: list[dict]) -> str:
    return hashlib.sha256(json.dumps(messages, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def lines_from(args: argparse.Namespace):
    if args.kubectl:
        out = subprocess.run(["kubectl", "logs", args.kubectl, "-n", args.namespace, "--tail=-1"],
                             capture_output=True, text=True, check=False).stdout
        yield from out.splitlines()
    else:
        for f in sorted(Path(args.dir).glob("*.jsonl")):
            yield from f.read_text(encoding="utf-8").splitlines()


def find(trace_id: str, args: argparse.Namespace) -> dict | None:
    for ln in lines_from(args):
        if trace_id in ln and ln.startswith("{"):
            try:
                rec = json.loads(ln)
            except ValueError:
                continue
            if rec.get("type") == "trace" and rec.get("trace_id") == trace_id:
                return rec
    return None


def render(t: dict) -> str:
    o = [f"TRACE {t['trace_id']}  {t['ts']}", "", f"query:      {t['query']}", f"rewritten:  {t['rewritten_query']}",
         f"embedding:  {t['embedding']}", f"collection: {t['collection']}", f"scope:      {t['scope']}",
         f"floor:      {t['floor']}", f"cache:      {t['cache']}", "", "retrieved (rank, score, chunk, document, version):"]
    for r in t["retrieved"]:
        o.append(f"  {r['rank']}. {r['score']:.4f}  {r['chunk_id']}  {r.get('doc_id')}  v={r.get('doc_version')} "
                 f"superseded={r.get('superseded')}  section={r['section']!r} page={r['page']}")
    o += ["", f"shown to the model (after floor and rails): {t['reranked_order']}", f"guardrails: {json.dumps(t['guardrails'])}", ""]
    if t["prompt"]:
        o.append("PROMPT (exact messages sent to the model):")
        for m in t["prompt"]:
            o += [f"--- {m['role']} ---", m["content"]]
        h = prompt_hash(t["prompt"])
        o += ["", f"prompt sha256 {t['prompt_sha256']}  recomputed {h}  -> {'hash OK' if h == t['prompt_sha256'] else 'hash MISMATCH'}"]
    else:
        o.append("PROMPT: none (no model call: abstained below the floor, dropped by a rail, or cache hit)")
    o += ["", f"model: {t['model']}", f"response: {json.dumps(t['response'], ensure_ascii=False)}",
          f"latency_ms: {t['latency_ms']}  tokens: {t['tokens']}"]
    return "\n".join(o)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["show"])
    ap.add_argument("trace_id")
    ap.add_argument("--dir", default="traces/samples")
    ap.add_argument("--kubectl", help="e.g. deploy/api: read the trace from `kubectl logs`")
    ap.add_argument("--namespace", default="rahbar")
    a = ap.parse_args()
    rec = find(a.trace_id, a)
    if rec is None:
        print(f"trace {a.trace_id} not found", file=sys.stderr)
        return 1
    print(render(rec))
    return 0


if __name__ == "__main__":
    sys.exit(main())
