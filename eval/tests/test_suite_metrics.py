"""Suite metrics, golden loader and typo noise (phase R4: AC4, AC6)."""

from __future__ import annotations

import json
import math

from suite import golden
from suite.component_level import score
from suite.e2e_level import SUPPORT_THRESHOLD
from suite.metrics import add_typos, ndcg_at_k, recall_at_k, reciprocal_rank, support_overlap
from suite.stochasticity import compare


def hit(source: str, section: str) -> dict:
    return {"source": source, "section": section}


R = [hit("a.pdf", "1.1"), hit("b.pdf", "2.2")]


def test_recall_mrr_ndcg_hand_computed() -> None:
    got = [hit("x.pdf", "9"), hit("a.pdf", "1.1 Title"), hit("c.pdf", "3"), hit("d.pdf", "4"), hit("b.pdf", "2.2 T")]
    assert recall_at_k(R, got, 3) == 0.5 and recall_at_k(R, got, 5) == 1.0
    assert reciprocal_rank(R, got) == 0.5
    assert math.isclose(ndcg_at_k(R, got), (1 / math.log2(3) + 1 / math.log2(6)) / (1 + 1 / math.log2(3)))
    assert reciprocal_rank(R, [hit("z", "1")]) == 0.0 and ndcg_at_k(R, [hit("z", "1")]) == 0.0
    assert recall_at_k([], got, 5) is None and ndcg_at_k([], got) is None
    assert reciprocal_rank(R, [hit("b.pdf", "2.2"), hit("a.pdf", "1.1")]) == 1.0
    assert ndcg_at_k([hit("a.pdf", "1.1")], [hit("a.pdf", "1.1"), hit("a.pdf", "1.1 again")]) == 1.0   # gains once
    assert recall_at_k([hit("a.pdf", "1.2")], [hit("a.pdf", "1.21")], 5) == 0.0                          # 1.2 is not 1.21


def test_typos_are_seeded_and_change_text() -> None:
    q = "What is the minimum attendance required to sit the final examination?"
    assert add_typos(q, 1) == add_typos(q, 1) and add_typos(q, 1) != add_typos(q, 2)
    assert any(add_typos(q, s) != q for s in range(5))
    assert add_typos("go to it", 1) == "go to it"


def test_support_overlap() -> None:
    ctx = "A student must attend at least 80% of lectures in each course."
    assert support_overlap("Students need 80% attendance of lectures.", ctx) >= SUPPORT_THRESHOLD - 0.2
    assert support_overlap("The fee is Rs 500 per credit hour.", ctx) < 0.2
    assert support_overlap("", ctx) == 0.0


def test_score_groups_and_ignores_unanswerable() -> None:
    rows = [{"id": "q1", "kind": "answerable", "relevant": [hit("a.pdf", "1.1")], "hard": True, "batch": "A", "tags": []},
            {"id": "q2", "kind": "unanswerable", "relevant": [], "batch": "A"}]
    out = score(rows, {"q1": [{"source": "a.pdf", "section": "1.1 x", "score": 0.9}], "q2": []})
    assert out["n"] == 1 and out["recall_at_5"] == 1.0 and out["hard"]["n"] == 1 and out["by_batch"]["A"]["mrr"] == 1.0


def test_golden_checks(tmp_path) -> None:
    rows = [{"id": f"q{i}", "kind": "answerable", "origin": "human", "hard": i < 5, "reviewed": True,
             "relevant": [{"source": "a", "section": "1", "page": 1}]} for i in range(15)]
    rows += [{"id": f"u{i}", "kind": "unanswerable", "origin": "synthetic", "reviewed": True, "relevant": [], "hard": False}
             for i in range(10)]
    assert golden.problems(rows) == []
    bad = [dict(r) for r in rows[:-1]]
    assert any("questions" in p for p in golden.problems(bad[:20]))
    broken = [dict(r) for r in rows]
    broken[0]["relevant"] = []
    assert any("ground-truth" in p for p in golden.problems(broken))
    p = tmp_path / "g.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows))
    assert len(golden.load(p)) == 25 and golden.counts(rows)["answerable"] == 15


def test_real_golden_file_structure() -> None:
    rows = golden.load()
    c = golden.counts(rows)
    assert c["questions"] >= 25 and c["answerable"] >= 15 and c["unanswerable"] >= 5 and c["hard"] >= 5 and c["human"] >= 8
    assert {r["batch"] for r in rows} == {"A", "B"} and len(golden.load(subset="A")) >= 25
    assert all(r["origin"] == "synthetic" for r in rows if r["id"].startswith("g"))


def test_stochasticity_compare() -> None:
    e = {"per_question": [{"id": "q", "answer": "x", "answered": True, "citations": [{"section": "1"}]}],
         "abstention_correctness": 1.0}
    a = {"component": {"clean": {}, "noisy": {}}, "e2e": e, "module": {}}
    b = {"component": {"clean": {}, "noisy": {}}, "e2e": {**e, "per_question": [{"id": "q", "answer": "y", "answered": True,
                                                                                "citations": [{"section": "1"}]}]}, "module": {}}
    out = compare(a, b)
    assert out["answers_differing_text"] == ["q"] and out["answers_differing_outcome_or_citations"] == []
