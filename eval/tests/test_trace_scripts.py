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
