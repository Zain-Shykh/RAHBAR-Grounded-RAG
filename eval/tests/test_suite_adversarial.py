"""Independent tester probes for R4 to R7 (WORKFLOW 6.1): metric edges, noise determinism, golden loader, gate, trace tools,
and the whole suite run offline against a fake API. No network, no model."""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml
from suite import gate, golden, module_level, run_suite
from suite.metrics import add_typos, ndcg_at_k, percentile, recall_at_k, reciprocal_rank

ROOT = Path(__file__).resolve().parents[2]


def H(s: str, x: str) -> dict:
    return {"source": s, "section": x}


# ---- metrics ---------------------------------------------------------------------------------------------------

def test_ndcg_more_relevant_than_k_reaches_one_when_top_k_all_relevant() -> None:
    rel = [H("a", str(i)) for i in range(1, 8)]
    got = [H("a", str(i)) for i in range(1, 6)]
    assert math.isclose(ndcg_at_k(rel, got, 5), 1.0)               # IDCG uses min(|R|, k)
    assert math.isclose(recall_at_k(rel, got, 5), 5 / 7)


def test_duplicate_relevant_entries_do_not_inflate_recall() -> None:
    rel = [H("a", "1"), H("a", "1")]
    assert recall_at_k(rel, [H("a", "1")], 5) == 1.0
    assert 0.0 < ndcg_at_k(rel, [H("a", "1")], 5) <= 1.0          # a duplicate gains once, so below 1 (golden has none)


def test_empty_retrieved_and_k_cutoffs() -> None:
    rel = [H("a", "1")]
    assert recall_at_k(rel, [], 5) == 0.0 and reciprocal_rank(rel, []) == 0.0 and ndcg_at_k(rel, []) == 0.0
    late = [H("x", "1")] * 5 + [H("a", "1")]
    assert reciprocal_rank(rel, late, 5) == 0.0 and recall_at_k(rel, late, 5) == 0.0 and recall_at_k(rel, late, 6) == 1.0
    assert reciprocal_rank(rel, [H("x", "1"), H("a", "1")], 5) == 0.5


def test_same_section_other_source_is_not_a_match_and_ties_keep_order() -> None:
    assert recall_at_k([H("a.pdf", "1.1")], [H("b.pdf", "1.1")], 5) == 0.0
    assert reciprocal_rank([H("a", "1"), H("b", "2")], [H("b", "2"), H("a", "1")]) == 1.0   # first hit decides


def test_percentile_edges() -> None:
    assert percentile([], 0.5) is None and percentile([7.0], 0.95) == 7.0
    assert percentile([1, 2, 3, 4], 0.5) == 2 and percentile([1, 2, 3, 4], 0.95) == 4 and percentile([4, 1, 3, 2], 1.0) == 4


# ---- typo noise ------------------------------------------------------------------------------------------------

def test_typos_edges_and_hash_seed_independence() -> None:
    assert add_typos("", 1) == "" and add_typos("a b c", 1) == "a b c"
    q = "What is the minimum attendance required to sit the final examination in a semester?"
    code = f"import sys; sys.path.insert(0, {str(ROOT / 'eval')!r}); from suite.metrics import add_typos; print(add_typos({q!r}, 7))"
    outs = {subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                           env={**os.environ, "PYTHONHASHSEED": h}).stdout for h in ("0", "1", "999")}
    assert len(outs) == 1 and outs.pop().strip() == add_typos(q, 7)
    for s in range(20):                                   # words of 3 letters or fewer are never touched
        assert add_typos("the cat sat on a mat", s) == "the cat sat on a mat"


# ---- golden loader ---------------------------------------------------------------------------------------------

def _rows(n_ans=15, n_un=5, reviewed=True) -> list[dict]:
    rows = [{"id": f"q{i}", "kind": "answerable", "origin": "human" if i < 8 else "synthetic", "hard": i < 5,
             "reviewed": reviewed, "relevant": [{"source": "a", "section": "1", "page": 1}]} for i in range(n_ans)]
    rows += [{"id": f"u{i}", "kind": "unanswerable", "origin": "synthetic", "hard": False, "reviewed": reviewed,
              "relevant": []} for i in range(n_un)]
    return rows


def test_check_exits_nonzero_when_a_minimum_is_short_and_zero_when_met(tmp_path, monkeypatch, capsys) -> None:
    good, bad = tmp_path / "good.jsonl", tmp_path / "bad.jsonl"
    rows = _rows(n_un=10)
    good.write_text("\n".join(json.dumps(r) for r in rows))
    bad.write_text("\n".join(json.dumps(r) for r in rows[:10]))
    monkeypatch.setattr(sys, "argv", ["g", "--check", "--golden", str(good), "--out", str(tmp_path / "c.json")])
    assert golden.main() == 0 and json.loads((tmp_path / "c.json").read_text())["problems"] == []
    monkeypatch.setattr(sys, "argv", ["g", "--check", "--golden", str(bad)])
    assert golden.main() == 1 and "PROBLEM" in capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", ["g", "--golden", str(bad)])        # without --check it only reports
    assert golden.main() == 0


def test_unreviewed_synthetic_questions_are_a_problem() -> None:
    assert any("synthetic_reviewed" in p for p in golden.problems(_rows(reviewed=False)))


def test_problems_flag_bad_relevant_and_duplicate_ids_and_bad_origin() -> None:
    rows = _rows(n_un=10)
    rows[0]["relevant"] = [{"source": "a", "section": "1"}]               # no page
    rows[1]["id"] = rows[2]["id"]
    rows[3]["origin"] = "robot"
    rows[-1]["relevant"] = [{"source": "a", "section": "1", "page": 1}]   # unanswerable with ground truth
    out = " | ".join(golden.problems(rows))
    assert "source, section and page" in out and "duplicate ids" in out and "origin must be" in out and "unanswerable must have" in out


def test_loader_skips_blank_lines_and_subset_filters(tmp_path) -> None:
    p = tmp_path / "g.jsonl"
    p.write_text('{"id":"a","batch":"A"}\n\n  \n{"id":"b","batch":"B"}\n{"id":"c"}\n')
    assert [r["id"] for r in golden.load(p)] == ["a", "b", "c"]
    assert [r["id"] for r in golden.load(p, "A")] == ["a", "c"] and [r["id"] for r in golden.load(p, "B")] == ["b"]


def test_loader_reports_a_malformed_line_instead_of_raising(tmp_path) -> None:   # T-1: was "raises"
    p = tmp_path / "g.jsonl"
    p.write_text('{"id":"a"}\n{not json\n')
    assert golden.load(p)[1]["_bad_json"] is True


def test_null_relevant_is_reported_not_a_crash() -> None:
    golden.problems([{"id": "a", "kind": "answerable", "origin": "human", "relevant": None}])


def test_missing_keys_are_reported_not_a_crash() -> None:
    golden.problems([{"id": "a"}])


def test_real_golden_relevant_sources_exist_and_pairs_meet_minimums() -> None:
    rows = golden.load()
    srcs = {rel["source"] for r in rows for rel in r.get("relevant", [])}
    have = {p.name for d in ("raw", "batch_b") for p in (ROOT / "corpus" / d).glob("*")}
    if (ROOT / "corpus" / "raw" / "_index.json").exists():   # corpus/raw is gitignored: absent in CI, so skipped there
        assert srcs <= have, srcs - have
    pairs = [json.loads(x) for x in (ROOT / "eval" / "embedding_pairs.jsonl").read_text().splitlines() if x.strip()]
    assert sum(p["kind"] == "paraphrase" for p in pairs) >= 15 and sum(p["kind"] == "unrelated" for p in pairs) >= 15
    assert all(r["page"] >= 1 for q in rows for r in q.get("relevant", []))
    assert len({q["id"] for q in rows}) == len(rows)


# ---- gate ------------------------------------------------------------------------------------------------------

CFG = yaml.safe_load((ROOT / "eval" / "gate.yaml").read_text())
BASE = {"meta": {"label": "b"}, "component": {"clean": {"recall_at_5": 0.9, "mrr": 0.8}},
        "e2e": {"faithfulness_supported_rate": 0.8, "abstention_correctness": 1.0, "citation_validity": 1.0, "latency_p95_s": 60}}


def test_gate_missing_baseline_metric_fails_relative_rules_only() -> None:
    base = json.loads(json.dumps(BASE))
    del base["component"]["clean"]["mrr"]
    code, lines = gate.run(base, BASE, CFG)
    assert code == 1 and any("missing in the baseline" in ln for ln in lines)
    ok, _ = gate.check({"metric": "e2e.citation_validity", "op": "at_least", "value": 0.95}, {}, BASE)
    assert ok                                                              # absolute rules need no baseline


def test_gate_nan_and_none_candidate_values_fail() -> None:
    c = json.loads(json.dumps(BASE))
    c["e2e"]["latency_p95_s"] = float("nan")
    c["component"]["clean"]["recall_at_5"] = None
    code, lines = gate.run(BASE, c, CFG)
    assert code == 1 and sum(ln.startswith("FAIL") for ln in lines) == 2


def test_gate_baseline_is_equal_to_itself_and_output_is_stable() -> None:
    assert gate.run(BASE, BASE, CFG) == gate.run(BASE, BASE, CFG) and gate.run(BASE, BASE, CFG)[0] == 0


@pytest.mark.parametrize("cfg_text", ["rules: [{metric: a.b}]", "not: rules", "rules: 5"])
def test_gate_bad_config_exits_2(tmp_path, monkeypatch, cfg_text) -> None:
    b, c, g = tmp_path / "b.json", tmp_path / "c.json", tmp_path / "g.yaml"
    b.write_text(json.dumps(BASE))
    c.write_text(json.dumps(BASE))
    g.write_text(cfg_text)
    monkeypatch.setattr(sys, "argv", ["gate", "--baseline", str(b), "--candidate", str(c), "--config", str(g)])
    assert gate.main() == 2


def test_gate_malformed_yaml_exits_2(tmp_path, monkeypatch) -> None:
    b, g = tmp_path / "b.json", tmp_path / "g.yaml"
    b.write_text(json.dumps(BASE))
    g.write_text("rules: [unclosed")
    monkeypatch.setattr(sys, "argv", ["gate", "--baseline", str(b), "--candidate", str(b), "--config", str(g)])
    assert gate.main() == 2


def test_gate_missing_files_exit_2(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["gate", "--baseline", str(tmp_path / "no"), "--candidate", str(tmp_path / "no2")])
    assert gate.main() == 2


def test_gate_config_every_rule_names_a_metric_that_compare_shows() -> None:
    from suite.compare import ROWS
    shown = {p for _, p, _ in ROWS}
    assert {r["metric"] for r in CFG["rules"]} <= shown


# ---- the whole suite offline -----------------------------------------------------------------------------------

class FakeEmbedder:
    def __init__(self, *a, **k) -> None:
        pass

    def embed(self, texts):
        out = []
        for t in texts:
            v = [0.0] * 8
            for w in t.lower().split():
                v[sum(map(ord, w)) % 8] += 1.0
            out.append(v)
        return out

    def version(self) -> str:
        return "fake@1"


class FakeApi:
    def __init__(self, *a, **k) -> None:
        self.calls: list[str] = []

    def ready(self):
        return {"ok": True}

    def retrieve(self, q, k=5):
        self.calls.append(q)
        return {"retrieved": [{"source": "a.pdf", "section": "1.1 Attendance", "page": 1, "score": 0.9,
                               "text": "Students need 80 percent attendance."}],
                "ms_retrieve": 3.0, "index_id": "ix", "embed_model": "fake"}

    def ask(self, q):
        un = "unans" in q
        return ({"request_id": "r", "answer": "I do not know." if un else "Students need 80 percent attendance.",
                 "answered_from_context": not un, "confidence": "high",
                 "citations": [] if un else [{"source": "a.pdf", "section": "1.1 Attendance", "page": 1}],
                 "retrieved": [{"source": "a.pdf", "section": "1.1 Attendance"}],
                 "_meta": {"outcome": "abstained" if un else "answered"}}, 0.5)


def test_one_command_writes_both_files_with_all_three_levels(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(module_level, "Embedder", FakeEmbedder)
    monkeypatch.setattr(run_suite, "Api", FakeApi)
    g = tmp_path / "g.jsonl"
    rows = [{"id": "q1", "question": "What is attendance?", "kind": "answerable", "origin": "human", "relevant":
             [{"source": "a.pdf", "section": "1.1", "page": 1}], "batch": "A", "expect": "80 percent"},
            {"id": "u1", "question": "unans question here", "kind": "unanswerable", "origin": "human", "relevant": [], "batch": "A"}]
    g.write_text("\n".join(json.dumps(r) for r in rows))
    path = run_suite.run_suite("http://x", "t", "A", 1, g, None, tmp_path / "out")
    res = json.loads(path.read_text())
    assert {"module", "component", "e2e"} <= set(res) and path.with_suffix(".md").exists()
    assert path.name.startswith("suite-") and path.name.endswith("-t.json")
    assert res["component"]["clean"]["recall_at_5"] == 1.0 and set(res["component"]["noise_delta"]) >= {"mrr", "recall_at_5"}
    e = res["e2e"]
    assert e["abstention_correctness"] == 1.0 and e["false_abstention_rate"] == 0.0 and e["citation_validity"] == 1.0
    assert e["faithfulness_supported_rate"] == 1.0 and e["expect_hit_rate"] == 1.0 and e["citations_total"] == 1
    assert res["module"]["pairs_paraphrase"] >= 15 and res["module"]["pairs_unrelated"] >= 15
    assert res["module"]["determinism_max_abs_diff"] == 0 and res["module"]["bytes_per_embedding_float32"] == 32
    md = path.with_suffix(".md").read_text()
    assert "Module level" in md and "Component level" in md and "End-to-end level" in md
    from suite.compare import table
    assert table(res, res).count("| 0.0000 |") + table(res, res).count("+0.0000") > 0
    assert gate.run(res, res, {"rules": [{"metric": "component.clean.recall_at_5", "op": "not_below_baseline", "value": 0}]})[0] == 0


def test_suite_exits_nonzero_and_writes_no_file_when_api_is_down(tmp_path, monkeypatch, capsys) -> None:
    import httpx

    class Down(FakeApi):
        def ready(self):
            raise httpx.ConnectError("refused")

    monkeypatch.setattr(run_suite, "Api", Down)
    monkeypatch.setattr(sys, "argv", ["s", "--api", "http://nope", "--out", str(tmp_path / "o")])
    assert run_suite.main() == 1 and "SUITE FAILED" in capsys.readouterr().err
    assert not list((tmp_path / "o").glob("*.json")) if (tmp_path / "o").exists() else True


# ---- trace tool and report -------------------------------------------------------------------------------------

def _load(name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


tool, report = _load("trace_tool"), _load("trace_report")


def _rec(i="t1", prompt=True, outcome="answered", ts=None):
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}] if prompt else None
    return {"type": "trace", "trace_id": i, "ts": ts or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "query": "q",
            "rewritten_query": None, "embedding": {}, "collection": {"name": "c", "index_id": "ix"}, "scope": None, "floor": None,
            "cache": "miss", "retrieved": [], "reranked_order": [], "guardrails": [], "prompt": msgs,
            "prompt_sha256": tool.prompt_hash(msgs) if msgs else None, "model": None, "tokens": {},
            "response": {"outcome": outcome}, "latency_ms": {}}


def test_tool_detects_every_prompt_edit_and_shows_none_for_abstained(tmp_path, monkeypatch, capsys) -> None:
    def show(rec):
        (tmp_path / "a.jsonl").write_text(json.dumps(rec) + "\n")
        monkeypatch.setattr(sys, "argv", ["x", "show", rec["trace_id"], "--dir", str(tmp_path)])
        assert tool.main() == 0
        return capsys.readouterr().out

    r = _rec()
    assert "hash OK" in show(r)
    r["prompt"][0]["content"] = "edited system rule"
    assert "hash MISMATCH" in show(r)
    r = _rec()
    r["prompt"].append({"role": "user", "content": "extra"})
    assert "hash MISMATCH" in show(r)
    r = _rec()
    r["prompt_sha256"] = "0" * 64
    assert "hash MISMATCH" in show(r)
    assert "PROMPT: none" in show(_rec("t9", prompt=False, outcome="abstained"))


def test_tool_ignores_other_ids_substring_hits_and_non_trace_lines(tmp_path, monkeypatch, capsys) -> None:
    (tmp_path / "a.jsonl").write_text(json.dumps(_rec("t12")) + "\n" + json.dumps({"type": "log", "trace_id": "t1"}) + "\n[x] t1\n")
    monkeypatch.setattr(sys, "argv", ["x", "show", "t1", "--dir", str(tmp_path)])
    assert tool.main() == 1 and "not found" in capsys.readouterr().err


def test_report_on_empty_dir_and_old_records_and_missing_retrieved(tmp_path) -> None:
    s = report.summarise(report.load(str(tmp_path), None))
    assert s["queries"] == 0 and s["abstention_rate"] is None and "queries: 0" in report.text(s)
    old = _rec("old", ts="2020-01-01T00:00:00Z")
    (tmp_path / "a.jsonl").write_text(json.dumps(old) + "\n" + json.dumps(_rec("new")) + "\n")
    assert [r["trace_id"] for r in report.load(str(tmp_path), 3600)] == ["new"]
    assert len(report.load(str(tmp_path), None)) == 2
    s = report.summarise(report.load(str(tmp_path), None))
    assert s["top1_similarity"]["min"] is None and s["cache_hit_rate"] == 0.0
    with pytest.raises(SystemExit):
        report.parse_window("soon")


def test_job_malformed_gate_yaml_exits_2(tmp_path, monkeypatch, capsys) -> None:
    from suite import job
    res = tmp_path / "r.json"
    res.write_text(json.dumps(BASE))
    (tmp_path / "g.yaml").write_text("rules: [unclosed")
    monkeypatch.setattr(job, "run_suite", lambda *a, **k: res)
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))
    monkeypatch.setenv("BASELINE", str(res))
    monkeypatch.setenv("GATE_CONFIG", str(tmp_path / "g.yaml"))
    assert job.main() == 2 and "GATE ERROR" in capsys.readouterr().err


def test_bad_json_line_is_a_problem(tmp_path) -> None:
    f = tmp_path / "g.jsonl"
    f.write_text('{"id": "a", "kind": "unanswerable", "origin": "human"}\n{oops\n')
    assert any("not valid JSON" in m for m in golden.problems(golden.load(f)))


def test_job_gate_only_skips_suite_and_follows_config(tmp_path, monkeypatch) -> None:
    from suite import job
    res = tmp_path / "r.json"
    res.write_text(json.dumps(BASE))
    cfg = tmp_path / "g.yaml"
    monkeypatch.setattr(job, "run_suite", lambda *a, **k: pytest.fail("suite must not run"))
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))
    monkeypatch.setenv("BASELINE", str(res))
    monkeypatch.setenv("GATE_ONLY", str(res))
    monkeypatch.setenv("GATE_CONFIG", str(cfg))
    monkeypatch.setenv("RUN_LABEL", "g")
    cfg.write_text("rules:\n- {metric: e2e.latency_p95_s, op: at_most, value: 1000, why: x}\n")
    assert job.main() == 0
    cfg.write_text("rules:\n- {metric: e2e.latency_p95_s, op: at_most, value: 0.001, why: x}\n")
    assert job.main() == 1
