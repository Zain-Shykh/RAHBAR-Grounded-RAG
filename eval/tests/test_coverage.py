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
