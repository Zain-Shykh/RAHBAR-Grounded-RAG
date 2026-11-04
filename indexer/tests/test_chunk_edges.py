"""Tester edge cases for the chunker (phase 6). Synthetic documents only: no corpus, no network."""

import random
import re

import pytest
from pipeline.chunk import chunk
from pipeline.models import Document, Page


def doc(*pages: str, source: str = "edge-doc.pdf") -> Document:
    return Document(source, "2026-06", False, [Page(source, i + 1, t) for i, t in enumerate(pages)])


def words(text: str) -> int:
    return len(text.split())


def toks(n: int, tag: str) -> str:
    return " ".join(f"{tag}x{i}" for i in range(n))


def test_heading_as_last_line_is_kept():
    cs = chunk(doc("1.1 First clause body text.\n\n2.1 Last Heading"), 400, 50)
    assert cs and "Last Heading" in cs[-1].text and cs[-1].section.startswith("2.1")


def test_only_heading_document():
    cs = chunk(doc("SEMESTER RULES"), 400, 50)
    assert len(cs) == 1 and cs[0].section == "SEMESTER RULES" and cs[0].text == "SEMESTER RULES"


def test_page_with_only_a_table():
    rows = "\n".join(f"A{i} | B{i}" for i in range(5))
    cs = chunk(doc(rows), 400, 50)
    assert len(cs) == 1 and cs[0].section == "edge-doc" and cs[0].page == 1
    assert cs[0].text.split("\n") == rows.split("\n")


def test_size_one_overlap_zero_one_word_per_chunk():
    cs = chunk(doc("1.1 a b c d"), 1, 0)
    assert len(cs) == 5
    assert all(words(c.text) <= 1 for c in cs)
    assert len({c.id for c in cs}) == len(cs)


def test_overlap_size_minus_one_never_exceeds_size():
    for size in (2, 3, 7, 50):
        cs = chunk(doc("1.1 Rule\n" + toks(300, "o")), size, size - 1)
        assert cs and all(words(c.text) <= size for c in cs), size


def test_overlap_is_tail_of_previous_chunk():
    cs = chunk(doc("1.1 Rule\n" + ". ".join(toks(7, f"s{i}") for i in range(60)) + "."), 40, 12)
    assert len(cs) >= 3
    for prev, nxt in zip(cs, cs[1:], strict=False):
        p, n = prev.text.split(), nxt.text.split()
        k = next((k for k in range(min(12, len(p), len(n)), 0, -1) if n[:k] == p[-k:]), 0)
        assert k >= 1, (prev.text, nxt.text)


def test_5000_word_line_is_split_and_complete():
    line = toks(5000, "L")
    cs = chunk(doc("1.1 H\n" + line), 400, 399)
    assert all(words(c.text) <= 400 for c in cs)
    seen = {w for c in cs for w in c.text.split()}
    assert set(line.split()) <= seen


def test_huge_size_gives_single_chunk():
    cs = chunk(doc("1.1 A b c.\n\n1.2 D e f."), 10**9, 10**9 - 1)
    assert [c.section for c in cs] == ["1.1 A b c.", "1.2 D e f."]


def test_bodyless_numbered_title_joins_next_section():
    """Documents DEV-003 behaviour: a one-line clause without a final period is a title."""
    cs = chunk(doc("1.1 A b c\n\n1.2 D e f."), 400, 50)
    assert len(cs) == 1 and cs[0].section == "1.2 D e f." and "1.1 A b c" in cs[0].text


def test_nbsp_and_tab_headings_normalised():
    cs = chunk(doc("1.1 Title here\nbody text"), 400, 50)
    assert cs[0].section == "1.1 Title here"
    cs = chunk(doc("1.1\tTitle\nbody text"), 400, 50)
    assert cs[0].section == "1.1 Title"


def test_unicode_all_caps_heading():
    cs = chunk(doc("ÀÉÎ ÕÜ NOTES\nbody text here"), 400, 50)
    assert cs[0].section == "ÀÉÎ ÕÜ NOTES"


def test_whitespace_only_pages_between_content():
    cs = chunk(doc("1.1 A text", " \t\n   ", "", "more text"), 400, 50)
    assert len(cs) == 1 and cs[0].page == 1 and "more" in cs[0].text


def test_input_document_not_mutated():
    d = doc("1.1 A\n" + toks(100, "m"), "1.2 B\n" + toks(100, "n"))
    before = [(p.source, p.page, p.text) for p in d.pages]
    chunk(d, 30, 5)
    assert [(p.source, p.page, p.text) for p in d.pages] == before


def test_chunks_never_cross_sections():
    pages = [f"{i}.1 Clause {i}\n" + toks(150, f"c{i}") for i in range(1, 6)]
    cs = chunk(doc(*pages), 60, 15)
    for c in cs:
        tags = {w.split("x")[0] for w in c.text.split() if re.fullmatch(r"c\dx\d+", w)}
        assert len(tags) <= 1, c.text
        if tags:
            assert c.section.startswith(f"{next(iter(tags))[1:]}.1")


LINES = [
    "1.1 Clause heading here", "2.3 Another Clause", "SEMESTER RULES", "V - EXAMINATION RULES",
    "Fee Refund Policy", "", "", "Dept | 12 | 34", "A | B", "a) list item", "2023 was a year.",
    " ", "16 Student Handbook 2026", "Plain prose sentence number here. Another one follows it.",
]


@pytest.mark.parametrize("seed", range(40))
def test_fuzz_invariants(seed):
    rng = random.Random(seed)
    n = [0]

    def line() -> str:
        base = rng.choice(LINES)
        if rng.random() < 0.3:
            n[0] += 1
            return base + " " + toks(rng.randint(1, 80), f"f{n[0]}_")
        return base

    pages = ["\n".join(line() for _ in range(rng.randint(0, 25))) for _ in range(rng.randint(0, 4))]
    d = doc(*pages)
    size = rng.choice([1, 2, 5, 20, 100, 400])
    overlap = rng.randint(0, size - 1)
    cs = chunk(d, size, overlap)
    assert [(c.id, c.text) for c in cs] == [(c.id, c.text) for c in chunk(d, size, overlap)]
    assert len({c.id for c in cs}) == len(cs)
    for c in cs:
        assert re.fullmatch(r"[a-z0-9._-]+-p\d{3}-c\d{3}", c.id)
        assert c.section and len(c.section) <= 80 and c.text.strip() and c.page >= 1
        rows = [ln for ln in c.text.split("\n") if " | " in ln]
        if words(c.text) > size:
            assert len(c.text.split("\n")) == 1 and len(rows) == 1, c.text  # single table row only
    src = {w for p in pages for w in p.split()}
    assert src <= {w for c in cs for w in c.text.split()}


def test_table_row_with_decimal_is_not_split():
    row = "Course | 3.5 Credit hours | x"
    cs = chunk(doc("1.1 T\n\n" + row), 400, 50)
    assert row in "\n".join(c.text for c in cs)
