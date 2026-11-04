"""Edge cases found by the phase 4 tester (extract, clean, verify)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pipeline import extract as ex
from pipeline.clean import clean, clean_text, repair_letter_spacing
from pipeline.extract import html_to_text, remove_repeating_lines, strip_front_matter
from pipeline.models import Document, Page
from pipeline.verify import VerifyError, verify

from test_extract_pdf import FakePage, _patch


def test_whitespace_only_pages_are_ocrd_and_stay_aligned(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    pages = [FakePage("text " * 20), FakePage(" \n\t "), FakePage("text " * 20), FakePage("")]
    _patch(monkeypatch, pages, calls)
    doc = ex.extract("/x/w.pdf", "1", False)
    assert calls == [2, 4]
    assert [p.page for p in doc.pages] == [1, 2, 3, 4]


def test_pdf_with_zero_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, [], [])
    assert ex.extract("/x/e.pdf", "1", False).pages == []


def test_one_page_pdf_header_logic_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, [FakePage("HEADER\nbody " * 10)], [])
    assert ex.extract("/x/one.pdf", "1", False).pages[0].text.startswith("HEADER")


def test_ocr_failure_all_pages_still_returns_document(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, [FakePage(""), FakePage("")] * 3, [])
    monkeypatch.setattr(ex, "_ocr_page", lambda p, n: (_ for _ in ()).throw(OSError("no tesseract")))
    doc = ex.extract("/x/z.pdf", "1", False)
    assert len(doc.pages) == 6 and all(p.ocr and p.text == "" for p in doc.pages)


def test_footer_equal_to_clause_number_line_survives() -> None:
    pages = [f"HEAD\nbody {i}\n9.2 Attendance rule\n" for i in range(6)]
    out = remove_repeating_lines(pages)
    assert all("9.2 Attendance rule" in p for p in out)


def test_all_blank_pages_do_not_crash() -> None:
    pages = ["", "  ", "\n", ""]
    assert remove_repeating_lines(pages) == pages
    assert remove_repeating_lines([]) == []


def test_html_nested_tables_keep_all_cell_text() -> None:
    html = ('<div class="main-content"><table><tr><td>a<td><table><tr><td>in1<td>in2</table>'
            '<td>out</table>')
    text = html_to_text(html)
    for s in ("a", "in1", "in2", "out"):
        assert s in text.split() or any(s in ln.split(" | ") for ln in text.split("\n"))


def test_html_br_in_cell_stays_on_one_row_and_entities_decoded() -> None:
    text = html_to_text('<div class="main-content"><table><tr><td>BS<br>CS<td>Rs&nbsp;1,000 &amp; more</table>')
    assert text == "BS CS | Rs 1,000 & more"


def test_html_unclosed_tags_and_nav_dropped() -> None:
    text = html_to_text("<body><nav>MENU<ul><li>x</nav><p>kept <b>bold<p>second")
    assert "MENU" not in text and "kept bold" in text and "second" in text


def test_html_empty_input() -> None:
    assert html_to_text("") == ""


def test_markdown_front_matter_without_close_is_kept_whole() -> None:
    md = "---\ndoc_version: 1\n# Heading\nbody"
    assert strip_front_matter(md) == md


def test_markdown_front_matter_only() -> None:
    assert strip_front_matter("---\na: 1\n---\n") == ""


def test_letter_spacing_very_long_line_is_fast_and_joined() -> None:
    assert repair_letter_spacing("a " * 20000 + "b") == "a" * 20000 + "b"


def test_letter_spacing_short_run_and_empty_untouched() -> None:
    assert repair_letter_spacing("") == ""
    assert repair_letter_spacing("a b c d") == "a b c d"
    assert repair_letter_spacing("x y z w V rest of words here and more") == "x y z w V rest of words here and more"


def test_clean_whitespace_only_page_and_input_not_mutated() -> None:
    doc = Document("d.pdf", "1", False, [Page("d.pdf", 1, " \x0c \n "), Page("d.pdf", 2, "a  b")])
    out = clean(doc)
    assert [p.text for p in out.pages] == ["", "a b"]
    assert doc.pages[1].text == "a  b"


def test_hyphen_at_end_of_text_is_kept() -> None:
    assert clean_text("trailing word-") == "trailing word-"


def test_hyphen_then_digit_line_keeps_the_digit() -> None:
    assert clean_text("Peshawar-\n2 campus") == "Peshawar-\n2 campus"
    assert clean_text("Peshawar-\n2") == "Peshawar-\n2"


def _index(d: Path, entries: list[dict[str, str]]) -> None:
    (d / "_index.json").write_text(json.dumps(entries), encoding="utf-8")


def test_verify_extra_file_on_disk_not_listed_is_ignored(tmp_path: Path) -> None:
    (tmp_path / "a.pdf").write_bytes(b"x")
    (tmp_path / "stray.pdf").write_bytes(b"y")
    _index(tmp_path, [{"file": "a.pdf", "sha256": hashlib.sha256(b"x").hexdigest()}])
    assert verify(str(tmp_path)) == 1


def test_verify_nonexistent_listed_file_reported_missing(tmp_path: Path) -> None:
    _index(tmp_path, [{"file": "ghost.pdf", "sha256": "0" * 64}])
    with pytest.raises(VerifyError, match="missing: ghost.pdf"):
        verify(str(tmp_path))


def test_verify_case_difference_in_name_is_reported(tmp_path: Path) -> None:
    (tmp_path / "A.pdf").write_bytes(b"x")
    _index(tmp_path, [{"file": "a.pdf", "sha256": hashlib.sha256(b"x").hexdigest()}])
    if (tmp_path / "a.pdf").exists():  # case-insensitive filesystem
        pytest.skip("case-insensitive filesystem")
    with pytest.raises(VerifyError, match="missing: a.pdf"):
        verify(str(tmp_path))


def test_verify_empty_index_returns_zero(tmp_path: Path) -> None:
    _index(tmp_path, [])
    assert verify(str(tmp_path)) == 0
