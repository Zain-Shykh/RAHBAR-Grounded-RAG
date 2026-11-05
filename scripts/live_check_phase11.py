#!/usr/bin/env python3
"""Live checks for phase 11 on the real stack. Manual: needs the API, Chroma, Redis Stack, Ollama.

  python scripts/live_check_phase11.py ask    --base http://localhost:8000 q07 [q07 ...]
  python scripts/live_check_phase11.py status [--chroma-port 8100] [--redis-url redis://localhost:6379]

`ask` posts each golden question id in order and prints X-Cache, X-Outcome, latency and the
request id, so `ask q07 q07 q07` shows MISS then HIT, HIT with a different request id and the
latency drop. `status` prints the live index_id (Chroma metadata), the cache indexes (FT._LIST)
and how many cache entries each holds. Run `status`, `ask`, re-index, wait past
INDEX_REFRESH_SECONDS, `ask`, `status`: the question is a MISS and the old index is gone.
Never starts or stops a service. Spec: docs/specs/phase-11-semantic-cache.md AC-1, AC-4.
"""

from __future__ import annotations

import argparse
import pathlib
import time

import httpx
import redis
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


def ask(base: str, ids: list[str], timeout: float) -> int:
    golden = {q["id"]: q["question"] for q in yaml.safe_load((ROOT / "eval/golden.yaml").read_text())["questions"]}
    last: dict[str, str] = {}
    for qid in ids:
        question = golden.get(qid, qid)     # an id, or a literal question
        t = time.perf_counter()
        r = httpx.post(f"{base}/api/ask", json={"question": question}, timeout=timeout)
        dt = time.perf_counter() - t
        body = r.json()
        same = "" if qid not in last else f" same_answer={body.get('answer') == last[qid]}"
        last[qid] = body.get("answer", "")
        print(f"{qid:<5} {r.status_code} X-Cache={r.headers.get('x-cache')} X-Outcome={r.headers.get('x-outcome')} "
              f"{dt * 1000:9.1f} ms request_id={body.get('request_id')}{same}")
    return 0


def status(chroma_port: int, redis_url: str) -> int:
    import chromadb

    col = chromadb.HttpClient(host="localhost", port=chroma_port).get_collection("rahbar")
    print("chroma index_id:", (col.metadata or {}).get("index_id"), "chunks:", col.count())
    r = redis.Redis.from_url(redis_url, socket_timeout=3)
    for name in sorted(n.decode() for n in r.execute_command("FT._LIST")):
        index_id = name.removeprefix("idx:cache:")
        print(f"redis index {name}: entries={len(r.keys(f'cache:{index_id}:*'))}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ask")
    a.add_argument("--base", default="http://localhost:8000")
    a.add_argument("--timeout", type=float, default=300)
    a.add_argument("ids", nargs="+")
    s = sub.add_parser("status")
    s.add_argument("--chroma-port", type=int, default=8100)
    s.add_argument("--redis-url", default="redis://localhost:6379")
    args = ap.parse_args()
    if args.cmd == "ask":
        return ask(args.base, args.ids, args.timeout)
    return status(args.chroma_port, args.redis_url)


if __name__ == "__main__":
    raise SystemExit(main())
