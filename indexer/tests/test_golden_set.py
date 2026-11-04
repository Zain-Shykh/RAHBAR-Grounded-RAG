"""Schema and mix checks for eval/golden.yaml (phase 3 spec, AC-1..AC-5).

No corpus, network or model needed: source names come from the committed corpus/MANIFEST.md.
Lives in indexer/tests because `make test` already runs it and eval/ has no test target.
"""

from __future__ import annotations

import collections
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "eval" / "golden.yaml"
TYPES = {"ordinary", "version", "exact", "abstain", "injection"}


@pytest.fixture(scope="module")
def questions() -> list[dict]:
    return yaml.safe_load(GOLDEN.read_text(encoding="utf-8"))["questions"]


def test_parses_and_has_18_unique_ids(questions: list[dict]) -> None:
    ids = [q["id"] for q in questions]
    assert len(ids) == 18
    assert ids == [f"q{i:02d}" for i in range(1, 19)]


def test_counts_by_type(questions: list[dict]) -> None:
    c = collections.Counter(q["type"] for q in questions)
    assert dict(c) == {"ordinary": 11, "version": 2, "exact": 2, "abstain": 2, "injection": 1}
    assert len(questions) >= 15 and c["ordinary"] >= 8  # R-GOL-1..5 minimums


def test_fields_valid(questions: list[dict]) -> None:
    manifest = (ROOT / "corpus" / "MANIFEST.md").read_text(encoding="utf-8")
    files = set(re.findall(r"`([\w.-]+\.(?:pdf|html))`", manifest))
    assert len(files) == 9
    for q in questions:
        assert q["type"] in TYPES, q["id"]
        assert isinstance(q["question"], str) and q["question"].strip(), q["id"]
        for r in q["relevant"]:
            assert r["source"] in files, (q["id"], r["source"])
            assert isinstance(r["section"], str) and r["section"].strip(), q["id"]


def test_relevant_items_have_page_comment() -> None:
    text = GOLDEN.read_text(encoding="utf-8")
    items = re.findall(r"^\s*- \{source:.*$", text, re.M)
    assert len(items) == 16  # 18 questions minus 2 abstain, one item each
    for line in items:
        assert re.search(r"#\s*(p\.\d+|html)\b", line), line


def test_abstain_questions(questions: list[dict]) -> None:
    for q in questions:
        if q["type"] == "abstain":
            assert q["must_abstain"] is True and q["relevant"] == [], q["id"]
        else:
            assert "must_abstain" not in q and q["relevant"], q["id"]
