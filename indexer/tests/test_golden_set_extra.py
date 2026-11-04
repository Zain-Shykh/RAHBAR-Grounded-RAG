"""Tester-added edge checks for eval/golden.yaml (phase 3). No corpus needed."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

GOLDEN = Path(__file__).resolve().parents[2] / "eval" / "golden.yaml"
TEXT = GOLDEN.read_text(encoding="utf-8")
QS = yaml.safe_load(TEXT)["questions"]
ITEM_KEYS = {"source", "section"}
QUESTION_KEYS = {"id", "type", "question", "relevant", "expect", "must_abstain"}


def test_no_unknown_keys_and_no_alternates() -> None:
    for q in QS:
        assert set(q) <= QUESTION_KEYS, (q["id"], set(q) - QUESTION_KEYS)
        for r in q["relevant"]:
            assert set(r) == ITEM_KEYS, (q["id"], r)


def test_questions_are_unique() -> None:
    texts = [q["question"].strip().lower() for q in QS]
    assert len(set(texts)) == len(texts)


def test_page_comment_kind_matches_source_type() -> None:
    for line in re.findall(r"^\s*- \{source:.*$", TEXT, re.M):
        src = re.search(r"source: (\S+?),", line).group(1)
        if src.endswith(".html"):
            assert re.search(r"#\s*html\s*$", line), line
        else:
            assert re.search(r"#\s*p\.[1-9]\d*\s*$", line), line


def test_clause_numbers_stay_strings() -> None:
    # bare 1.21 / 4.3 would load as float; 1.10 would lose its zero
    for q in QS:
        for r in q["relevant"]:
            assert type(r["section"]) is str, q["id"]
    by_id = {q["id"]: q for q in QS}
    assert by_id["q14"]["relevant"][0]["section"] == "1.21"
    assert by_id["q12"]["relevant"][0]["section"] == "4.25"


def test_version_pair_same_clause_different_documents() -> None:
    v = [q for q in QS if q["type"] == "version"]
    assert len(v) == 2
    secs = {q["relevant"][0]["section"] for q in v}
    srcs = {q["relevant"][0]["source"] for q in v}
    assert len(secs) == 1 and len(srcs) == 2
    assert "undergraduate-academic-rules-aug-2023.pdf" in srcs


def test_expect_present_for_answerable_questions_only() -> None:
    for q in QS:
        if q["type"] == "abstain":
            assert "expect" not in q, q["id"]
        else:
            assert isinstance(q["expect"], str) and q["expect"].strip(), q["id"]


@pytest.mark.parametrize("word", ["hostel", "curfew"])
def test_abstain_topic_is_still_the_absent_one(word: str) -> None:
    ab = " ".join(q["question"].lower() for q in QS if q["type"] == "abstain")
    assert word in ab


def test_injection_question_carries_injection_and_real_relevant() -> None:
    q = next(q for q in QS if q["type"] == "injection")
    assert "ignore" in q["question"].lower() and q["relevant"]
