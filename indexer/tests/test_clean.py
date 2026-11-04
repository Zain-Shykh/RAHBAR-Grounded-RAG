"""Clean stage rules (phase 4 spec 5.3, AC-7, AC-8)."""

from __future__ import annotations

from pipeline.clean import clean, clean_text, repair_letter_spacing
from pipeline.models import Document, Page


def test_unicode_and_whitespace() -> None:
    t = clean_text("ﬁne print​  with\t\ttabs\x0c\nnext­line")
    assert t == "fine print with tabs\nnextline"


def test_hyphen_join_lowercase_only() -> None:
    assert clean_text("the exam-\nination hall") == "the examination hall"
    assert clean_text("Chiniot-\nFaisalabad") == "Chiniot-\nFaisalabad"
    assert clean_text("Phase-\n2 work") == "Phase-\n2 work"


def test_page_number_lines_dropped() -> None:
    assert clean_text("text\n12\nPage 3 of 85\n- 7 -\nmore") == "text\nmore"


def test_blank_lines_collapse() -> None:
    assert clean_text("a\n\n\n\n\nb") == "a\n\nb"


def test_clause_numbers_untouched() -> None:
    t = "92. Reporting\n9.2 Reporting\n1.21 Attendance 100%"
    assert clean_text(t) == t


def test_table_row_and_separator_kept() -> None:
    t = "Islamabad 19 14 46 | 236\nA+ 4.00 B- 2.67"
    assert clean_text(t) == t


def test_letter_spacing_repaired() -> None:
    assert "75%" in repair_letter_spacing("a r e 7 5 % . Fa i l u r e t o m e e t")


def test_letter_spacing_guard() -> None:
    for line in ("A+ 4.00 B- 2.67", "Grade A B C D", "1 2 3"):
        assert repair_letter_spacing(line) == line


def test_clean_returns_new_document() -> None:
    doc = Document("x.pdf", "v", False, [Page("x.pdf", 1, "a-\nb  c", ocr=True)])
    out = clean(doc)
    assert out is not doc and doc.pages[0].text == "a-\nb  c"
    assert out.pages[0].text == "ab c" and out.pages[0].ocr and out.pages[0].page == 1
    assert (out.source, out.doc_version, out.superseded) == ("x.pdf", "v", False)
