"""The one command (R3-B-9): module, component and end-to-end levels, one timestamped result file.

    python -m eval.suite.run_suite --api http://localhost:8000 --label baseline [--subset A]

Writes eval/results/suite-<UTC timestamp>-<label>.json and a sibling .md summary table. Exit 0 when the suite ran;
the release gate is a separate step (eval/suite/gate.py). Run from the repository root.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

from . import component_level, e2e_level, golden, module_level
from .client import Api

HERE = Path(__file__).resolve().parents[1]


def git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              cwd=HERE).stdout.strip() or "unknown"
    except OSError:
        return "unknown"


def table(res: dict) -> str:
    m, c, e = res["module"], res["component"], res["e2e"]
    cl, nz, d = c["clean"], c["noisy"], c["noise_delta"]
    f = lambda x, p=3: "n/a" if x is None else f"{x:.{p}f}"  # noqa: E731
    lines = [f"# Suite result {res['meta']['label']} ({res['meta']['timestamp']})", "",
             f"index `{res['meta']['index_id']}`, embed `{m['model']}`, questions {e['n']}, subset `{res['meta']['subset']}`, "
             f"git `{res['meta']['git']}`", "",
             "## Module level (embedding)", "", "| metric | value |", "| --- | --- |",
             f"| paraphrase mean cosine ({m['pairs_paraphrase']} pairs) | {f(m['paraphrase_mean'])} |",
             f"| unrelated mean cosine ({m['pairs_unrelated']} pairs) | {f(m['unrelated_mean'])} |",
             f"| gap | {f(m['gap'])} |",
             f"| embed time per chunk, median / p95 ms ({m['chunks_timed']} chunks) | {f(m['ms_per_chunk_median'], 1)} / {f(m['ms_per_chunk_p95'], 1)} |",
             f"| memory per embedding (float32 bytes) | {m['bytes_per_embedding_float32']} |",
             f"| determinism, largest abs difference | {m['determinism_max_abs_diff']:.2e} |", "",
             "## Component level (retrieval, answerable questions)", "",
             "| metric | clean | with typos | change |", "| --- | --- | --- | --- |"]
    for k, label in (("recall_at_3", "recall@3"), ("recall_at_5", "recall@5"), ("mrr", "MRR"), ("ndcg_at_5", "nDCG@5")):
        lines.append(f"| {label} (n={cl['n']}) | {f(cl[k])} | {f(nz[k])} | {d[k]['abs']:+.3f} |")
    lines += [f"| retrieval latency median / p95 ms | {f(c['retrieval_ms_median'], 1)} / {f(c['retrieval_ms_p95'], 1)} | | |", "",
              "## End-to-end level (answers)", "", "| metric | value |", "| --- | --- |",
              f"| faithfulness, support overlap mean (answered n={e['answered_n']}) | {f(e['faithfulness_overlap_mean'])} |",
              f"| faithfulness, share supported at {e['support_threshold']} | {f(e['faithfulness_supported_rate'])} |",
              f"| abstention correctness (n={e['abstention_n']}) | {f(e['abstention_correctness'])} |",
              f"| false abstention rate (answerable) | {f(e['false_abstention_rate'])} |",
              f"| citation validity ({e['citations_total']} citations) | {f(e['citation_validity'])} |",
              f"| expected-text hit rate | {f(e['expect_hit_rate'])} |",
              f"| fallback rate | {f(e['fallback_rate'])} |",
              f"| latency p50 / p95 seconds | {f(e['latency_p50_s'], 1)} / {f(e['latency_p95_s'], 1)} |"]
    return "\n".join(lines) + "\n"


def run_suite(api_url: str, label: str, subset: str, seed: int, golden_path: Path, host: str | None,
              out_dir: Path, skip_e2e: bool = False, limit: int = 0) -> Path:
    random.seed(seed)
    api = Api(api_url, host)
    rows = golden.load(golden_path, subset)
    if limit > 0:   # smoke run (fresh-cluster rehearsal), never used for a gate decision: one unanswerable question plus the
        un = [r for r in rows if r["kind"] == "unanswerable"][:1]   # first answerable ones, so every gate metric exists
        rows = [r for r in rows if r["kind"] != "unanswerable"][:max(0, limit - len(un))] + un
    problems = golden.problems(golden.load(golden_path))
    if problems and subset == "all":
        print("golden set problems (continuing):", problems, file=sys.stderr)
    ready = api.ready()
    comp = component_level.run(api, rows, seed)
    texts = comp.pop("chunk_texts")
    mod = module_level.run(chunk_texts=texts)
    e2e = e2e_level.run(api, rows) if not skip_e2e else {}
    probe = api.retrieve(rows[0]["question"], 1)
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    res = {"meta": {"label": label, "timestamp": ts, "git": git_sha(), "subset": subset, "seed": seed,
                    "llm_seed_env": os.environ.get("LLM_SEED"), "api": api_url, "ready": ready,
                    "index_id": probe["index_id"], "embed_model": probe["embed_model"],
                    "golden": str(golden_path.name), "golden_counts": golden.counts(rows)},
           "module": mod, "component": comp, "e2e": e2e}
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"suite-{ts}-{label}.json"
    path.write_text(json.dumps(res, indent=2) + "\n")
    if e2e:
        path.with_suffix(".md").write_text(table(res))
        print(table(res))
    print("wrote", path)
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default=os.environ.get("API_URL", "http://localhost:8000"))
    ap.add_argument("--host")
    ap.add_argument("--label", default=os.environ.get("RUN_LABEL", "run"))
    ap.add_argument("--subset", default="A", choices=["A", "B", "all"])
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--golden", type=Path, default=HERE / "golden.jsonl")
    ap.add_argument("--out", type=Path, default=Path(os.environ.get("RESULTS_DIR", HERE / "results")))
    ap.add_argument("--skip-e2e", action="store_true")
    ap.add_argument("--limit", type=int, default=int(os.environ.get("QUESTION_LIMIT", "0")))
    a = ap.parse_args()
    try:
        run_suite(a.api, a.label, a.subset, a.seed, a.golden, a.host, a.out, a.skip_e2e, a.limit)
    except Exception as exc:   # never present a partial file as a result (R5-AC7)
        print(f"SUITE FAILED: {exc!r}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
