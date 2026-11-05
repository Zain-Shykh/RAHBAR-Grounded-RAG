"""Pure-data tests for eval/run_eval.py (no network, model or cluster)."""

import json
import sys

import httpx
import pytest

import run_eval as r


def G(src="a.pdf", sec="1"):
    return {"source": src, "section": sec}


# ---- AC-2 section matching
@pytest.mark.parametrize("gold,ret,ok", [
    ("1.21", "1.21 Attendance", True),
    ("5", "5.4 Academic Warning", True),
    ("1.2", "1.21 Attendance", False),
    ("1.21", "1.21: Attendance", True),
    ("1.21", "1.21.1", True),
    ("1.21", "1.2", False),
    ("  Fee   Refund POLICY ", "fee refund policy", True),
    ("VI – SEMESTER RULES", "VI - SEMESTER RULES", True),
    ("VI - SEMESTER RULES", "VI — semester rules", True),
    ("5", "50 Other", False),
])
def test_section_matches(gold, ret, ok):
    assert r.section_matches(gold, ret) is ok


def test_source_must_match():
    assert r.recall_at_k([G("a.pdf", "1")], [G("b.pdf", "1")], 3) == 0.0


# ---- AC-3 recall
def test_recall_empty_relevant_is_none():
    assert r.recall_at_k([], [G()], 3) is None


def test_recall_partial():
    rel = [G("a", "1"), G("a", "2")]
    assert r.recall_at_k(rel, [G("a", "1 x"), G("a", "9")], 3) == 0.5


def test_recall_rank_cutoff():
    ret = [G("a", "9"), G("a", "8"), G("a", "7"), G("a", "1")]
    assert r.recall_at_k([G("a", "1")], ret, 3) == 0.0
    assert r.recall_at_k([G("a", "1")], ret, 5) == 1.0


def test_recall_short_and_empty_retrieved():
    assert r.recall_at_k([G("a", "1")], [], 5) == 0.0


# ---- AC-4 citation validity
def resp(cits, retrieved, answered=True, outcome=None, cache=None):
    return {"citations": cits, "retrieved": retrieved, "answered_from_context": answered,
            "_meta": {"outcome": outcome, "cache": cache}}


def test_citation_none_without_citations():
    assert r.citation_validity(resp([], [G()])) is None


def test_citation_all_valid():
    assert r.citation_validity(resp([G("a", "1")], [G("a", "1")])) == 1.0


def test_citation_half_valid_and_wrong_section():
    assert r.citation_validity(resp([G("a", "1"), G("a", "2")], [G("a", "1")])) == 0.5
    assert r.citation_validity(resp([G("a", "1")], [G("a", "1.1")])) == 0.0


# ---- AC-5 summarise
def row(id, type, rel, retrieved, cits=(), must=False, answered=True, outcome=None, secs=1.0):
    return {"id": id, "type": type, "must_abstain": must, "relevant": rel, "expect": None,
            "response": resp(list(cits), retrieved, answered, outcome), "seconds": secs}


def rows():
    return [
        row("o1", "ordinary", [G("a", "1")], [G("a", "1 x")], [G("a", "1 x")], secs=1),
        row("o2", "ordinary", [G("a", "2")], [G("a", "9"), G("a", "8"), G("a", "7"), G("a", "2")],
            [G("a", "9"), G("a", "zz")], secs=2),
        row("e1", "exact", [G("a", "3"), G("a", "4")], [G("a", "3")], secs=3),
        row("x1", "abstain", [], [G("a", "1")], must=True, answered=False, secs=4),
        row("x2", "abstain", [], [G("a", "1")], must=True, answered=False, outcome="fallback", secs=5),
        row("x3", "abstain", [], [G("a", "1")], must=True, answered=True, secs=6),
    ]


def test_summarise_values():
    s = r.summarise(rows())
    assert s["recall_at_3"] == pytest.approx((1 + 0 + 0.5) / 3)
    assert s["recall_at_5"] == pytest.approx((1 + 1 + 0.5) / 3)
    assert s["by_type"]["ordinary"] == {"recall_at_3": 0.5, "recall_at_5": 1.0, "n": 2}
    assert s["by_type"]["exact"]["n"] == 1
    assert "abstain" not in s["by_type"]
    assert (s["citations_total"], s["citations_valid"]) == (3, 2)
    assert s["citation_validity"] == pytest.approx(2 / 3)
    assert s["must_abstain_total"] == 3
    assert s["must_abstain_failed"] == ["x3"]
    assert s["abstention_correctness"] == pytest.approx(2 / 3)
    assert s["must_abstain_fallback"] == 1
    assert s["fallback_rate"] == pytest.approx(1 / 6)
    assert s["latency_p50"] == 3 and s["latency_p95"] == 6
    assert len(s["per_question"]) == 6
    assert all("recall" in k for k in s if k.startswith("recall"))


def test_summarise_no_scored_no_abstain():
    s = r.summarise([row("o", "ordinary", [], [], secs=1)])
    assert s["recall_at_5"] is None and s["abstention_correctness"] is None
    assert s["citation_validity"] is None and s["by_type"] == {}


def test_summarise_missing_meta():
    rw = row("o", "ordinary", [G("a", "1")], [G("a", "1")])
    del rw["response"]["_meta"]
    assert r.summarise([rw])["fallback_rate"] == 0.0


# ---- AC-6 gate
GOOD = {"recall_at_5": 0.8, "citation_validity": 1.0, "abstention_correctness": 1.0,
        "must_abstain_failed": []}


def test_gate_pass_and_no_baseline():
    assert r.gate(GOOD, {"recall_at_5": 0.8}) == []
    assert r.gate({**GOOD, "recall_at_5": 0.0}, None) == []


def test_gate_recall_drop():
    assert len(r.gate({**GOOD, "recall_at_5": 0.74}, {"recall_at_5": 0.8})) == 1


def test_gate_recall_boundary_passes():
    assert r.gate({**GOOD, "recall_at_5": 0.75}, {"recall_at_5": 0.80}) == []


def test_gate_abstention():
    m = r.gate({**GOOD, "abstention_correctness": 0.5, "must_abstain_failed": ["q9"]}, None)
    assert len(m) == 1 and "q9" in m[0]


def test_gate_citation():
    assert len(r.gate({**GOOD, "citation_validity": 0.94}, None)) == 1
    assert r.gate({**GOOD, "citation_validity": 0.95}, None) == []


def test_gate_none_values_skip():
    assert r.gate({"recall_at_5": None, "citation_validity": None,
                   "abstention_correctness": None}, {"recall_at_5": 0.8}) == []


# ---- AC-7 ask headers
def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_ask_captures_headers():
    def h(req):
        return httpx.Response(200, json={"answer": "x"},
                              headers={"X-Outcome": "answered", "X-Cache": "MISS"})
    out = r.ask(_client(h), "http://t", "q?")
    assert out["answer"] == "x" and out["_meta"] == {"outcome": "answered", "cache": "MISS"}


def test_ask_headers_absent():
    out = r.ask(_client(lambda req: httpx.Response(200, json={})), "http://t", "q?")
    assert out["_meta"] == {"outcome": None, "cache": None}


# ---- AC-8 main
GOLD = "questions:\n  - {id: a, question: 'What is it?', relevant: [{source: s, section: '1'}]}\n"
ABST = "questions:\n  - {id: z, question: 'Hostel?', must_abstain: true, relevant: []}\n"


def run_main(monkeypatch, tmp_path, gold, fake_ask, *extra, baseline=None):
    g = tmp_path / "g.yaml"
    g.write_text(gold)
    out, bl = tmp_path / "out.json", tmp_path / "bl.json"
    if baseline is not None:
        bl.write_text(json.dumps(baseline))
    monkeypatch.setattr(r, "ask", fake_ask)
    monkeypatch.setattr(sys, "argv", ["run_eval", "--api", "http://t", "--golden", str(g),
                                      "--out", str(out), "--baseline", str(bl), *extra])
    return r.main(), out, bl


def test_main_aborts_on_ask_error(monkeypatch, tmp_path, capsys):
    def boom(*a, **k):
        raise httpx.ConnectError("refused")
    code, out, _ = run_main(monkeypatch, tmp_path, GOLD, boom)
    assert code == 1 and not out.exists()
    assert "question a" in capsys.readouterr().out


def test_main_pass_writes_results(monkeypatch, tmp_path):
    def ok(*a, **k):
        return resp([], [G("s", "1 x")])
    code, out, _ = run_main(monkeypatch, tmp_path, GOLD, ok)
    assert code == 0 and json.loads(out.read_text())["recall_at_5"] == 1.0


def test_update_baseline_refused_when_abstention_fails(monkeypatch, tmp_path):
    def leak(*a, **k):
        return resp([], [], answered=True)
    code, out, bl = run_main(monkeypatch, tmp_path, ABST, leak, "--update-baseline")
    assert code == 1 and out.exists() and not bl.exists()


def test_update_baseline_allowed_on_recall_drop_only(monkeypatch, tmp_path):
    def miss(*a, **k):
        return resp([], [G("s", "9")])
    code, out, bl = run_main(monkeypatch, tmp_path, GOLD, miss, "--update-baseline",
                             baseline={"recall_at_5": 1.0})
    assert code == 1 and json.loads(bl.read_text())["recall_at_5"] == 0.0


def test_golden_label_is_repo_relative(tmp_path):
    assert r.golden_label(r.HERE / "golden.yaml") == "eval/golden.yaml"
    assert r.golden_label(tmp_path / "g.yaml") == (tmp_path / "g.yaml").resolve().as_posix()
