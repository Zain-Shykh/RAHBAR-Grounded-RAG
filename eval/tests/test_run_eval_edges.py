"""Tester break-it cases for eval/run_eval.py (no network, model or cluster)."""

import json
import sys

import httpx
import pytest

import run_eval as r
from test_run_eval import G, GOLD, resp, row, run_main


# ---- section matching edges
@pytest.mark.parametrize("gold,ret,ok", [
    ("", "", True),
    ("1", "", False),
    ("", "1.21 x", False),                 # empty golden section must not match everything
    ("1.21 Attendance and Leave", "1.21", False),   # golden longer than retrieved
    ("1.21", "1.21-Attendance", False),
    ("Ⅵ", "vi", True),                     # NFKC roman numeral
    ("A‐B", "a-b", True),             # hyphen U+2010
    ("A−B", "a-b", True),             # minus sign U+2212
    ("1.21 Attendance", "1.21 attendance", True),  # nbsp
])
def test_section_matches_edges(gold, ret, ok):
    assert r.section_matches(gold, ret) is ok


# ---- recall edges
def test_recall_duplicate_golden_items_count_each():
    rel = [G("a", "1"), G("a", "1")]
    assert r.recall_at_k(rel, [G("a", "1")], 3) == 1.0
    assert r.recall_at_k(rel + [G("a", "2")], [G("a", "1")], 3) == pytest.approx(2 / 3)


def test_recall_one_retrieved_matches_two_golden():
    assert r.recall_at_k([G("a", "1.2"), G("a", "1.3")], [G("a", "1.2 x")], 3) == 0.5


def test_recall_k_zero_is_zero():
    assert r.recall_at_k([G("a", "1")], [G("a", "1")], 0) == 0.0


# ---- citation edges
def test_citation_response_without_retrieved_or_citations_keys():
    assert r.citation_validity({}) is None
    assert r.citation_validity({"citations": [G("a", "1")], "retrieved": None}) == 0.0
    assert r.citation_validity({"citations": None, "retrieved": [G()]}) is None


def test_citation_source_mismatch_invalid():
    assert r.citation_validity(resp([G("a", "1")], [G("b", "1")])) == 0.0


def test_citation_section_is_exact_not_folded():
    # 5.8 rule is exact equality; the runner must not be more lenient than the API
    assert r.citation_validity(resp([G("a", "VI – X")], [G("a", "VI - X")])) == 0.0


def test_citation_duplicates_counted_each():
    assert r.citation_validity(resp([G("a", "1"), G("a", "1")], [G("a", "1")])) == 1.0


# ---- summarise edges
def test_summarise_empty_rows():
    s = r.summarise([])
    assert s["fallback_rate"] == 0.0 and s["latency_p50"] is None and s["recall_at_5"] is None


def test_summarise_response_without_retrieved():
    rw = row("o", "ordinary", [G("a", "1")], [])
    del rw["response"]["retrieved"]
    assert r.summarise([rw])["recall_at_5"] == 0.0


def test_summarise_must_abstain_with_null_answered_counts_as_leak():
    rw = row("x", "abstain", [], [], must=True)
    rw["response"]["answered_from_context"] = None
    s = r.summarise([rw])
    assert s["must_abstain_failed"] == ["x"] and s["abstention_correctness"] == 0.0


def test_summarise_abstain_row_with_relevant_is_scored_and_abstain_checked():
    rw = row("x", "abstain", [G("a", "1")], [G("a", "1")], must=True, answered=False)
    s = r.summarise([rw])
    assert s["abstention_correctness"] == 1.0 and s["recall_at_5"] == 1.0


def test_summarise_single_row_percentiles():
    s = r.summarise([row("o", "ordinary", [], [], secs=2.5)])
    assert s["latency_p50"] == s["latency_p95"] == 2.5


def test_summarise_result_is_json_serialisable():
    json.dumps(r.summarise([row("o", "ordinary", [G("a", "1")], [G("a", "1")])]))


# ---- gate edges
def test_gate_all_three_fail_together():
    m = r.gate({"recall_at_5": 0.1, "citation_validity": 0.5, "abstention_correctness": 0.0,
                "must_abstain_failed": ["q"]}, {"recall_at_5": 0.9})
    assert len(m) == 3


def test_gate_baseline_missing_keys_or_null():
    res = {"recall_at_5": 0.1}
    assert r.gate(res, {}) == []
    assert r.gate(res, {"recall_at_5": None}) == []


def test_gate_recall_improvement_passes():
    assert r.gate({"recall_at_5": 0.9}, {"recall_at_5": 0.5}) == []


def test_gate_results_missing_keys():
    assert r.gate({}, {"recall_at_5": 0.9}) == []


# ---- ask edges
def test_ask_http_500_raises():
    with httpx.Client(transport=httpx.MockTransport(lambda q: httpx.Response(500))) as c:
        with pytest.raises(httpx.HTTPStatusError):
            r.ask(c, "http://t", "q")


def test_ask_non_json_200_raises_valueerror():
    with httpx.Client(transport=httpx.MockTransport(
            lambda q: httpx.Response(200, text="<html>"))) as c:
        with pytest.raises(ValueError):
            r.ask(c, "http://t", "q")


def test_ask_trailing_slash_in_api():
    seen = []

    def h(req):
        seen.append(str(req.url))
        return httpx.Response(200, json={})
    with httpx.Client(transport=httpx.MockTransport(h)) as c:
        r.ask(c, "http://t/", "q")
    assert seen == ["http://t/api/ask"]


# ---- main edges
def test_main_aborts_on_http_500(monkeypatch, tmp_path, capsys):
    def boom(*a, **k):
        raise httpx.HTTPStatusError("500", request=httpx.Request("POST", "http://t"),
                                    response=httpx.Response(500))
    code, out, bl = run_main(monkeypatch, tmp_path, GOLD, boom, "--update-baseline")
    assert code == 1 and not out.exists() and not bl.exists()
    assert "question a" in capsys.readouterr().out


def test_main_aborts_on_non_json_body(monkeypatch, tmp_path):
    def bad(*a, **k):
        raise json.JSONDecodeError("x", "", 0)
    code, out, _ = run_main(monkeypatch, tmp_path, GOLD, bad)
    assert code == 1 and not out.exists()


def test_main_aborts_midway_writes_nothing(monkeypatch, tmp_path):
    gold = GOLD + "  - {id: b, question: 'Two?', relevant: []}\n"
    calls = []

    def flaky(*a, **k):
        calls.append(1)
        if len(calls) == 2:
            raise httpx.ReadTimeout("slow")
        return resp([], [G("s", "1")])
    code, out, bl = run_main(monkeypatch, tmp_path, gold, flaky, "--update-baseline")
    assert code == 1 and not out.exists() and not bl.exists()


def test_main_empty_golden_exits(monkeypatch, tmp_path):
    for body in ("", "questions: []\n", "questions:\n", "other: 1\n"):
        with pytest.raises(SystemExit) as e:
            run_main(monkeypatch, tmp_path, body, lambda *a, **k: {})
        assert e.value.code not in (0, None)


def test_main_relevant_null_treated_as_no_relevant(monkeypatch, tmp_path):
    gold = "questions:\n  - {id: n, question: 'q?', relevant: null}\n"
    code, out, _ = run_main(monkeypatch, tmp_path, gold, lambda *a, **k: resp([], []))
    assert code == 0 and json.loads(out.read_text())["recall_at_5"] is None


def test_main_response_without_retrieved_or_citations(monkeypatch, tmp_path):
    code, out, _ = run_main(monkeypatch, tmp_path, GOLD,
                            lambda *a, **k: {"answered_from_context": True})
    assert code == 0 or code == 1
    assert json.loads(out.read_text())["recall_at_5"] == 0.0


def test_main_update_baseline_refused_on_citation_failure(monkeypatch, tmp_path):
    def bad_cite(*a, **k):
        return resp([G("s", "nope")], [G("s", "1")])
    code, out, bl = run_main(monkeypatch, tmp_path, GOLD, bad_cite, "--update-baseline")
    assert code == 1 and out.exists() and not bl.exists()


def test_main_update_baseline_writes_on_clean_pass(monkeypatch, tmp_path):
    code, out, bl = run_main(monkeypatch, tmp_path, GOLD,
                             lambda *a, **k: resp([], [G("s", "1")]), "--update-baseline")
    assert code == 0 and json.loads(bl.read_text())["recall_at_5"] == 1.0


def test_main_baseline_with_missing_keys_does_not_crash(monkeypatch, tmp_path):
    code, _, _ = run_main(monkeypatch, tmp_path, GOLD, lambda *a, **k: resp([], [G("s", "1")]),
                          baseline={"unrelated": 1})
    assert code == 0


def test_main_malformed_baseline_does_not_traceback(monkeypatch, tmp_path):
    g = tmp_path / "g.yaml"
    g.write_text(GOLD)
    bl = tmp_path / "bl.json"
    bl.write_text("{not json")
    monkeypatch.setattr(r, "ask", lambda *a, **k: resp([], [G("s", "1")]))
    monkeypatch.setattr(sys, "argv", ["run_eval", "--api", "http://t", "--golden", str(g),
                                      "--out", str(tmp_path / "o.json"), "--baseline", str(bl)])
    try:
        code = r.main()
    except SystemExit as e:
        code = e.code
    assert code == 1
