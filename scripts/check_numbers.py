"""Cross-check the headline numbers quoted in the docs against the committed results and config.

Run: python scripts/check_numbers.py   (exit 1 on any mismatch). Output is kept in
docs/evidence/final-numbers-check.txt.
"""
import json
import pathlib
import re
import sys

R = pathlib.Path(__file__).resolve().parent.parent
res = json.loads((R / "eval/results.json").read_text())
base = json.loads((R / "eval/baseline.json").read_text())
cm = (R / "k8s/base/configmap.yaml").read_text()
read = lambda p: (R / p).read_text()  # noqa: E731
bad = 0


def check(label, ok, detail=""):
    global bad
    bad += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {label} {detail}")


def cfg(key):
    return re.search(rf'^\s*{key}:\s*"?([^"\n#]+)"?', cm, re.M).group(1).strip()


def has(doc, pat):
    return re.search(pat, read(doc), re.S) is not None


check("results.json == baseline.json", res == base)
for k, v in [("CHUNK_SIZE", "400"), ("CHUNK_OVERLAP", "50"), ("TOP_K", "5"), ("RELEVANCE_FLOOR", "0.70"),
             ("EMBED_MODEL", "nomic-embed-text"), ("LLM_MODEL", "llama3.2:3b")]:
    check(f"configmap {k}", cfg(k) == v, f"= {cfg(k)}")
check("golden questions = 18", len(res["per_question"]) == 18, f"({len(res['per_question'])})")
r5, r3 = res["recall_at_5"], res["recall_at_3"]
check("recall@3 == recall@5 == 0.875", r3 == r5 == 0.875)
bt = {k: round(v["recall_at_5"], 3) for k, v in res["by_type"].items()}
check("by type", bt == {"ordinary": 0.909, "version": 1.0, "exact": 0.5, "injection": 1.0}, str(bt))
check("citations 16/16, validity 1.0", (res["citations_valid"], res["citations_total"], res["citation_validity"]) == (16, 16, 1.0))
check("abstention 2/2, fallback 0", res["abstention_correctness"] == 1.0 and res["must_abstain_total"] == 2 and res["fallback_rate"] == 0)
check("latency p50 39.0 / p95 138.6", (round(res["latency_p50"], 1), round(res["latency_p95"], 1)) == (39.0, 138.6))
for c in ("200-25", "400-50", "600-100"):
    t = json.loads(read(f"eval/tuning/chunk-{c}.json"))
    check(f"tuning {c} recall@5 0.875", t["recall_at_5"] == 0.875)
for c, n in (("200-25", 1103), ("400-50", 981), ("600-100", 952)):
    m = re.search(r'"chunks": (\d+)', read(f"eval/tuning/chunk-{c}.index.txt"))
    check(f"tuning {c} chunks {n}", m and int(m.group(1)) == n, f"({m and m.group(1)})")
ix = json.loads(re.search(r"\{.*chunked total.*\}", read("eval/tuning/chunk-400-50.index.txt")).group(0))
check("400/50 words 75644 / 73051 / amp 1.04", (ix["words"], ix["source_words"], ix["amplification"]) == (75644, 73051, 1.04))

P, E = "docs/PIPELINE.md", "docs/ENGINEERING-NOTES.md"
for doc, pat, label in [
    (P, r"recall@3 = recall@5 = 0\.875", "PIPELINE recall"),
    (P, r"citation validity 1\.000 \(16 of 16\)", "PIPELINE citations"),
    (P, r"p50 39\.0 s, p95 138\.6 s", "PIPELINE latency"),
    (P, r"75 644 over 73 051", "PIPELINE words"),
    (P, r"\| 200 \| 25 \|.*\| 1103 \|", "PIPELINE 200/25 chunks"),
    (P, r"\| 600 \| 100 \|.*\| 952 \|", "PIPELINE 600/100 chunks"),
    (P, r"Shipped: 0\.70", "PIPELINE floor"),
    (P, r"981 chunks", "PIPELINE 981"),
    (P, r"980", "PIPELINE 980 (DEV-010)"),
    (E, r"\*\*981\*\*", "NOTES 981"),
    (E, r"0\.875 \(14 of 16\)", "NOTES overall recall"),
    (E, r"p50 39\.0 s, p95 138\.6 s", "NOTES latency"),
    (E, r"DEV-010", "NOTES 980 vs 981 pointer"),
    ("README.md", r"`RELEVANCE_FLOOR` \| `0\.70`", "README floor"),
    ("README.md", r"`TOP_K` \| `5`", "README top_k"),
]:
    check(f"{label}", has(doc, pat))
print("MISMATCHES:", bad)
sys.exit(1 if bad else 0)
