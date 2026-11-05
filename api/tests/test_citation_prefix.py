"""DEV-005: a cited section may be the leading clause number of exactly one retrieved section."""

from __future__ import annotations

import json

import pytest

from app.schemas import Citation, Passage
from app.services.validate import citation_matches, validate


def ps_(i: int, section: str, source: str = "a.pdf") -> Passage:
    return Passage(chunk_id=f"c{i}", text="t", source=source, section=section, page=i, score=0.9)


def test_abbreviated_section_resolves_to_the_exact_retrieved_one() -> None:
    ps = [ps_(1, "4.3 The normal course load is 5 courses."), ps_(2, "1.17 Normal semester course load")]
    assert citation_matches(Citation(source="a.pdf", section="4.3"), ps) is ps[0]
    assert citation_matches(Citation(source="a.pdf", section="1.17", page=9), ps) is ps[1]


def test_a_truncated_heading_ending_at_a_word_boundary_is_accepted() -> None:
    ps = [ps_(1, "4.3 The normal course load is 5 courses.")]
    assert citation_matches(Citation(source="a.pdf", section="4.3 The normal"), ps) is ps[0]


@pytest.mark.parametrize("cited", ["4", "4.", "4.3 Th", "5.1", "", "  "])
def test_non_matching_or_loose_prefixes_are_rejected(cited: str) -> None:
    ps = [ps_(1, "4.3 The normal course load is 5 courses."), ps_(2, "4.31 Other")]
    assert citation_matches(Citation(source="a.pdf", section=cited), ps) is None


def test_ambiguous_prefix_is_rejected_and_other_source_never_matches() -> None:
    ps = [ps_(1, "4.3 First"), ps_(2, "4.3 Second")]
    assert citation_matches(Citation(source="a.pdf", section="4.3"), ps) is None
    assert citation_matches(Citation(source="b.pdf", section="4.3 First"), ps) is None


def test_validate_rewrites_an_abbreviated_citation_to_the_exact_section() -> None:
    raw = json.dumps({"reasoning": "r", "answer": "5 courses", "answered_from_context": True,
                      "confidence": "high", "citations": [{"source": "a.pdf", "section": "4.3", "page": 99}]})
    out = validate(raw, [ps_(1, "4.3 The normal course load is 5 courses.")])
    assert [(c.section, c.page) for c in out.citations] == [("4.3 The normal course load is 5 courses.", 1)]
