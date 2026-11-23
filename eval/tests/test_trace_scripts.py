"""trace_tool and trace_report (phase R6: AC3, AC4)."""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def mod(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


tool, report = mod("trace_tool"), mod("trace_report")


def rec(i, score, outcome="answered", cache="miss", inj=0, gen=100.0):
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": f"u{i}"}]
    return {"type": "trace", "trace_id": f"t{i}", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "query": "q",
            "rewritten_query": None, "embedding": {}, "collection": {"name": "rahbar", "index_id": "ix"}, "scope": {},
            "floor": {}, "cache": cache, "retrieved": [{"rank": 1, "score": score, "chunk_id": "c", "doc_id": "d.pdf",
            "section": "1", "page": 1}], "reranked_order": ["c"], "guardrails": [{"rail": "injection_scan"}] * inj,
            "prompt": msgs, "prompt_sha256": tool.prompt_hash(msgs), "model": {}, "tokens": {},
            "response": {"outcome": outcome}, "latency_ms": {"scope": 1, "embed": 2, "cache": 0, "retrieve": 5,
            "guardrails": 0, "generate": gen, "total": gen + 10}}


def write(tmp, rows):
    (tmp / "traces-1.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n")


def test_tool_finds_trace_and_checks_hash(tmp_path, capsys, monkeypatch):
    write(tmp_path, [rec(1, .8), rec(2, .9)])
    import sys
    monkeypatch.setattr(sys, "argv", ["x", "show", "t2", "--dir", str(tmp_path)])
    assert tool.main() == 0
    out = capsys.readouterr().out
    assert "TRACE t2" in out and "hash OK" in out and "--- user ---\nu2" in out
    r = rec(3, .7)
    r["prompt"][1]["content"] = "tampered"
    write(tmp_path, [r])
    monkeypatch.setattr(sys, "argv", ["x", "show", "t3", "--dir", str(tmp_path)])
    tool.main()
    assert "hash MISMATCH" in capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", ["x", "show", "nope", "--dir", str(tmp_path)])
    assert tool.main() == 1


def test_report_numbers_match_independent_computation(tmp_path):
    rows = [rec(1, .8, cache="miss", gen=100), rec(2, .9, cache="hit", gen=0), rec(3, .3, outcome="abstained", inj=2, gen=0),
            rec(4, .85, cache="miss", gen=300)]
    write(tmp_path, rows)
    s = report.summarise(report.load(str(tmp_path), None))
    assert s["queries"] == 4 and s["abstention_rate"] == 0.25 and s["injection_flags"] == 2
    assert s["cache_hit_rate"] == 1 / 4 and s["cache_lookups"] == 4
    assert s["top1_similarity"]["min"] == .3 and s["top1_similarity"]["max"] == .9
    assert s["latency_ms"]["generate"]["p95"] == 300 and s["latency_ms"]["generate"]["p50"] == 0
    assert sum(s["top1_similarity"]["histogram"].values()) == 4
    assert report.parse_window("2h") == 7200 and report.load(str(tmp_path), 0.0001) in ([], report.load(str(tmp_path), 0.0001))
    assert "queries: 4" in report.text(s)


def test_trace_tool_follows_a_cache_hit_to_the_original_request(tmp_path, capsys) -> None:
    import json
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scripts"))
    import trace_tool
    base = {"type": "trace", "ts": "t", "query": "q", "rewritten_query": None, "embedding": {}, "collection": {}, "scope": {},
            "retrieved": [], "reranked_order": [], "floor": {}, "guardrails": [], "model": "m", "latency_ms": {}, "tokens": {},
            "response": {}}
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
    orig = {**base, "trace_id": "A", "cache": "miss", "prompt": msgs, "prompt_sha256": trace_tool.prompt_hash(msgs),
            "attempt_log": [{"attempt": 1, "result": "ok", "prompt_sha256": "x" * 64, "hint": None}]}
    hit = {**base, "trace_id": "B", "cache": "hit", "prompt": None, "prompt_sha256": None, "cached_from": "A"}
    (tmp_path / "t.jsonl").write_text(json.dumps(orig) + "\n" + json.dumps(hit) + "\n")
    sys.argv = ["trace_tool", "show", "B", "--dir", str(tmp_path)]
    assert trace_tool.main() == 0
    out = capsys.readouterr().out
    assert "CACHE HIT" in out and "ORIGINAL REQUEST A" in out and "hash OK" in out and "attempt 1: result=ok" in out


def test_release_guard_refuses_a_failed_or_unrecorded_gate(tmp_path, monkeypatch) -> None:
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scripts"))
    import release_guard as g
    monkeypatch.setattr(g, "DECISIONS", tmp_path / "d.json")
    bad, good = tmp_path / "bad.txt", tmp_path / "good.txt"
    bad.write_text("candidate /results/x.json\nGATE FAILED: 5 of 6 rules pass\nexit 1\n")
    good.write_text("candidate /results/y.json\nGATE PASSED: 6 of 6 rules pass\nexit 0\n")
    g.record("c_bad", str(bad))
    g.record("c_good", str(good))
    assert g.check("c_bad") == 1 and g.check("c_good") == 0 and g.check("never_ran") == 1


def test_extra_metrics_gold_citation_and_noncanned_abstention() -> None:
    import sys
    sys.path.insert(0, str(ROOT))
    from eval.suite.e2e_level import cites_gold, extra_metrics
    rel = [{"source": "a.pdf", "section": "4.3 The normal course load", "page": 1}]
    assert cites_gold([{"source": "a.pdf", "section": "4.3 The normal course load is 5 courses. A final"}], rel)
    assert not cites_gold([{"source": "b.pdf", "section": "4.3 The normal course load"}], rel)
    per = [{"id": "x", "kind": "answerable", "answered": True, "citations": [{"source": "b.pdf", "section": "9"}], "answer": "a"},
           {"id": "y", "kind": "unanswerable", "answered": False, "citations": [], "answer": "None of the fee is refunded."}]
    out = extra_metrics(per, [{"id": "x", "relevant": rel}, {"id": "y", "relevant": []}])
    assert out["gold_citation_rate"] == 0.0 and out["abstained_noncanned"][0]["id"] == "y"
