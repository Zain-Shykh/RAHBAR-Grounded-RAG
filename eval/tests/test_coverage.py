"""Coverage script logic and the live query file (phase R10: AC1, AC2)."""

from __future__ import annotations

import json
from pathlib import Path

from suite.coverage import coverage

HERE = Path(__file__).resolve().parents[1]


def test_live_queries_shape() -> None:
    rows = [json.loads(ln) for ln in (HERE / "live_queries.jsonl").read_text().splitlines()]
    assert len(rows) >= 40 and sum(r["in_domain"] for r in rows) in range(26, 31) and sum(not r["in_domain"] for r in rows) >= 12
    golden = {json.loads(ln)["question"].lower() for ln in (HERE / "golden.jsonl").read_text().splitlines()}
    assert not ({r["query"].lower() for r in rows} & golden)
    assert all(r["expected_topic"] for r in rows)


def test_coverage_share_topics_and_threshold() -> None:
    live = [{"id": "a", "query": "qa", "expected_topic": "t1", "in_domain": True},
            {"id": "b", "query": "qb", "expected_topic": "t2", "in_domain": True}]
    golden = [{"id": "g1", "question": "g1"}]
    vecs = {"qa": [1.0, 0.0], "qb": [0.0, 1.0], "g1": [1.0, 0.1]}
    r = coverage(live, golden, vecs, 0.9)
    assert r["share"] == 0.5 and r["uncovered_topics"] == {"t2": ["b"]} and r["per_query"][0]["nearest_golden"] == "g1"
    assert coverage(live, golden, vecs, 0.0)["share"] == 1.0
    assert coverage(live, golden, vecs, 0.999)["share"] == 0.0


def test_main_exit_code_below_and_above_target(tmp_path, monkeypatch) -> None:
    """AC2: exit 1 below the target, 0 at or above it, with a trimmed golden set and a fake embedder."""
    import suite.coverage as cov

    class Fake:
        def embed(self, texts):
            return [[1.0, 0.0] if "cover" in t else [0.0, 1.0] for t in texts]

        def version(self):
            return "fake"

    monkeypatch.setattr(cov, "Embedder", Fake)
    live = tmp_path / "live.jsonl"
    live.write_text("".join(json.dumps(r) + "\n" for r in [
        {"id": "a", "query": "cover me", "expected_topic": "t1", "in_domain": True},
        {"id": "b", "query": "other", "expected_topic": "t2", "in_domain": True}]))
    gold = tmp_path / "g.jsonl"
    gold.write_text(json.dumps({"id": "g1", "question": "cover q", "kind": "answerable", "hard": False, "origin": "human",
                                "reviewed": True, "relevant": [{"source": "s", "section": "1", "page": 1}], "expect": None,
                                "batch": "A", "tags": [], "must_abstain": False}) + "\n")
    for target, code in ((0.85, 1), (0.5, 0)):
        cfg = tmp_path / "c.yaml"
        cfg.write_text(f"threshold: 0.9\ntarget: {target}\n")
        monkeypatch.setattr("sys.argv", ["c", "--live", str(live), "--golden", str(gold), "--config", str(cfg)])
        assert cov.main() == code
