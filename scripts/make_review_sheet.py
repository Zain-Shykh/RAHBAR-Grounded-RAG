#!/usr/bin/env python3
"""Write eval/REVIEW_SHEET.md: questions, expected answer and the real passage from the live index (R12, D-144).

    kubectl port-forward svc/api 18003:8000 -n rahbar &
    kubectl port-forward svc/chroma 18100:8000 -n rahbar &
    python scripts/make_review_sheet.py g19 g20 ...   [--base http://localhost:18003] [--chroma-port 18100]

Passage text: a read-only Chroma `get` on the live collection (source + page + section). The API's top-10 for the question is
reported next to it (does the system find the ground truth). Needs the venv (chromadb, eval.suite).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))


def retrieve(base: str, q: str, k: int = 10) -> list[dict]:
    r = urllib.request.Request(f"{base}/api/retrieve", json.dumps({"question": q, "k": k}).encode(),
                               {"content-type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=60))["retrieved"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--base", default="http://localhost:18003")
    ap.add_argument("--chroma-port", type=int, default=18100)
    a = ap.parse_args()
    import chromadb
    from eval.suite.metrics import matches
    col = chromadb.HttpClient(host="localhost", port=a.chroma_port).get_collection("rahbar")
    rows = {r["id"]: r for r in map(json.loads, (ROOT / "eval/golden.jsonl").read_text(encoding="utf-8").splitlines())}
    out = ["# Review sheet: 8 synthetic golden questions (D-144)\n",
           "Passages below were read from the live Chroma collection `rahbar` on the cluster (read-only), not typed. "
           "For each question judge: (1) is the question clear, (2) does the passage really contain the answer, "
           "(3) is the expected answer right. About 10 seconds each. g22 was replaced by g23: g22 now abstains in the live system (the 2027 amendment supersedes the fee page, D-143), so it is a poor review candidate; its version-aware pair g51/g52 covers that topic.\n"]
    for i in a.ids:
        r = rows[i]
        assert r["origin"] == "synthetic" and r["kind"] == "answerable", i
        rel = r["relevant"][0]
        got = col.get(where={"$and": [{"source": rel["source"]}, {"page": rel["page"]}]}, include=["documents", "metadatas"])
        chunks = [(d, m) for d, m in zip(got["documents"], got["metadatas"]) if matches(rel, m)]
        assert chunks, f"{i}: ground truth not in the live index"
        top = retrieve(a.base, r["question"])
        rank = next((c["rank"] for c in top if matches(rel, c)), None)
        found = f"the API finds it at rank {rank} of 10" if rank else "the API does NOT return it in its top 10 (a retrieval miss, not a bad question)"
        quoted = "\n".join("> " + ln for d, _ in chunks for ln in d.strip().splitlines())
        out.append(f"## {i}\n\n**Question:** {r['question']}\n\n**Expected answer:** {r.get('expect') or '(none recorded; judge from the passage)'}\n\n"
                   f"**Ground truth:** `{rel['source']}`, section `{rel['section']}`, page {rel['page']} (doc_version {chunks[0][1].get('doc_version')}); {found}\n\n"
                   f"**Passage:**\n\n{quoted}\n")
    out.append("""## Reply format

Send one message in this shape (ids you accept in `reviewed`, anything you want changed in `fixes`):

```
reviewed: g19 g20 g21 g23 g28 g29 g30 g33 ; fixes: g23 wording "..." ; none
```

The session applies the fixes to `scripts/build_golden_jsonl.py` (wording or expected answer), regenerates the file, then runs:

```
python scripts/mark_reviewed.py g19 g20 g21 g23 g28 g29 g30 g33 && python -m eval.suite.golden --check
```

`mark_reviewed.py` sets `reviewed: true` for the ids given only, and refuses any `human` question.
""")
    (ROOT / "eval/REVIEW_SHEET.md").write_text("\n".join(out), encoding="utf-8")
    print("wrote eval/REVIEW_SHEET.md")


if __name__ == "__main__":
    main()
