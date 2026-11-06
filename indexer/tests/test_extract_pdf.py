"""PDF-side extract rules: OCR trigger, header and footer removal (phase 4 spec 5.1, 5.2)."""

from __future__ import annotations

from pipeline.extract import needs_ocr, remove_repeating_lines, strip_front_matter


def test_needs_ocr_boundary() -> None:
    assert needs_ocr("x" * 29)
    assert not needs_ocr("x" * 30)
    assert needs_ocr("  \n\t ")
    assert needs_ocr("a b " * 7)  # 14 non-space characters
    assert needs_ocr("x " * 29)  # whitespace does not count towards the 30
    assert not needs_ocr("x " * 30)


def _page(body: str, n: int) -> str:
    return f"UNIVERSITY HEADER\n{body}\nTitle of book {n}"


def test_repeating_header_and_footer_removed() -> None:
    words = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot"]
    pages = [_page(w, i) for i, w in enumerate(words, 1)]
    assert remove_repeating_lines(pages) == words


def test_numbered_clause_in_edge_survives() -> None:
    pages = [f"HEAD\n1.21 Attendance\nrest {i}\nfoot {i}" for i in range(6)]
    out = remove_repeating_lines(pages)
    assert all("1.21 Attendance" in p for p in out)
    assert all(not p.startswith("HEAD") for p in out)


def test_minority_line_kept() -> None:
    pages = [f"line a{i}\nline b{i}\nline c{i}\nline d{i}" for i in range(6)]
    pages[0] = "Chapter 2 Faculty\n" + pages[0]
    pages[1] = "Chapter 2 Faculty\n" + pages[1]
    assert remove_repeating_lines(pages)[0].startswith("Chapter 2 Faculty")


def test_body_line_equal_to_header_not_removed() -> None:
    mids = ["red", "green", "blue", "cyan", "pink", "gold", "gray", "teal"]
    pages = []
    for k in range(5):
        body = [f"{m}-{'x' * k}" for m in mids]
        body.insert(4, "HEAD")  # mid-page, outside the top and bottom three
        pages.append("\n".join(["HEAD", *body, "foot"]))
    out = remove_repeating_lines(pages)
    assert all(p.split("\n").count("HEAD") == 1 for p in out)
    assert all(p.split("\n")[0].startswith("red") for p in out)


def test_short_documents_untouched() -> None:
    pages = ["H\na", "H\nb", "H\nc"]
    assert remove_repeating_lines(pages) == pages


def test_front_matter() -> None:
    md = "---\ndoc_version: 2026\nsuperseded: false\n---\n# Title\n\ntext"
    assert strip_front_matter(md) == "# Title\n\ntext"
    assert strip_front_matter("# No front matter") == "# No front matter"
    assert strip_front_matter("---\nunclosed\n# x") == "---\nunclosed\n# x"


# ---- extract() with a fake pdfplumber (no PDFs, no tesseract) ----
import pytest  # noqa: E402
from pipeline import extract as ex  # noqa: E402


class FakePage:
    def __init__(self, text: str = "", cols: list[str] | None = None, words_x1: float = 0.0) -> None:
        self.text, self.cols, self.width, self.height = text, cols or [], 600.0, 800.0
        self.words_x1 = words_x1
        self.crops: list[tuple[float, ...]] = []

    def extract_text(self) -> str | None:
        return self.text or None

    def extract_words(self) -> list[dict[str, float]]:
        return [{"x1": self.words_x1}] if self.words_x1 else []

    def crop(self, box: tuple[float, ...], strict: bool = True) -> FakePage:
        assert strict is False  # spread pages crop beyond the MediaBox
        self.crops.append(box)
        return FakePage(self.cols[len(self.crops) - 1])

    def flush_cache(self) -> None:
        pass


class FakePdf:
    def __init__(self, pages: list[FakePage]) -> None:
        self.pages = pages

    def __enter__(self) -> FakePdf:
        return self

    def __exit__(self, *a: object) -> None:
        pass


def _patch(monkeypatch: pytest.MonkeyPatch, pages: list[FakePage], ocr_calls: list[int]) -> None:
    monkeypatch.setattr(ex.pdfplumber, "open", lambda path: FakePdf(pages))

    def fake_ocr(path: str, n: int) -> str:
        ocr_calls.append(n)
        return f"ocr text of page {n} " + "word " * 10

    monkeypatch.setattr(ex, "_ocr_page", fake_ocr)


def test_ocr_called_only_for_empty_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    pages = [FakePage("real text " * 10), FakePage(""), FakePage("tiny"), FakePage("more text " * 10)]
    _patch(monkeypatch, pages, calls)
    doc = ex.extract("/x/a.pdf", "2026", False)
    assert calls == [2, 3]
    assert [p.ocr for p in doc.pages] == [False, True, True, False]
    assert [p.page for p in doc.pages] == [1, 2, 3, 4]
    assert doc.source == "a.pdf" and doc.doc_version == "2026" and doc.superseded is False


def test_ocr_failure_is_not_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, [FakePage(""), FakePage("fine text " * 10)], [])

    def boom(path: str, n: int) -> str:
        raise RuntimeError("tesseract missing")

    monkeypatch.setattr(ex, "_ocr_page", boom)
    doc = ex.extract("/x/b.pdf", "v", True)
    assert doc.pages[0].text == "" and doc.pages[0].ocr
    assert doc.pages[1].text.startswith("fine text")


def test_column_split_reads_columns_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    name = "prospectus-2026-academic-rules-and-regulations.pdf"
    page = FakePage("interleaved " * 5, cols=["left col " * 5, "mid col " * 5, "right col " * 5])
    _patch(monkeypatch, [page], [])
    doc = ex.extract(f"/x/{name}", "2026", False)
    assert page.crops == [(0.0, 0, 220.0, 800.0), (220.0, 0, 397.0, 800.0), (397.0, 0, 600.0, 800.0)]
    t = doc.pages[0].text
    assert t.index("left col") < t.index("mid col") < t.index("right col")
    assert "interleaved" not in t


@pytest.mark.parametrize("name,gutter", [("student-handbook-jun-2026.pdf", 404.0),
                                         ("academic-rules-handbook-jun-2026.pdf", 400.0)])
def test_handbook_spread_split_into_two_pages(monkeypatch: pytest.MonkeyPatch, name: str, gutter: float) -> None:
    page = FakePage("interleaved " * 5, cols=["left page " * 5, "right page " * 5], words_x1=756.0)
    _patch(monkeypatch, [page], [])
    doc = ex.extract(f"/x/{name}", "2026", False)
    assert page.crops == [(0.0, 0, gutter, 800.0), (gutter, 0, 757.0, 800.0)]
    t = doc.pages[0].text
    assert t.index("left page") < t.index("right page") and "interleaved" not in t


def test_single_page_handbook_keeps_page_width(monkeypatch: pytest.MonkeyPatch) -> None:
    page = FakePage("x", cols=["only left " * 5, ""], words_x1=363.0)
    _patch(monkeypatch, [page], [])
    doc = ex.extract("/x/student-handbook-jun-2026.pdf", "2026", False)
    assert page.crops[-1][2] == 600.0 and doc.pages[0].text.startswith("only left")


def test_markdown_and_unknown_suffix(tmp_path: object) -> None:
    from pathlib import Path

    d = Path(str(tmp_path))
    (d / "f.md").write_text("---\ndoc_version: 1\n---\n# H\n\nbody", encoding="utf-8")
    doc = ex.extract(str(d / "f.md"), "1", False)
    assert doc.pages[0].text == "H\n\nbody" and doc.pages[0].page == 1
    with pytest.raises(ValueError):
        ex.extract(str(d / "f.docx"), "1", False)
    with pytest.raises(FileNotFoundError):
        ex.extract(str(d / "missing.md"), "1", False)


def test_footer_with_and_without_page_number_match() -> None:
    pages = [f"body {w}\nmore {w}\nlast {w}\nBook Title 2026" + (f" {i}" if i % 2 else "")
             for i, w in enumerate(["aa", "bb", "cc", "dd", "ee", "ff"])]
    assert all("Book Title" not in p for p in remove_repeating_lines(pages))


def test_md_heading_markers_are_dropped() -> None:
    from pipeline.extract import strip_md_markers
    assert strip_md_markers("# T\n\n## 1. Attendance\ntext # not a heading\n####### seven") == \
        "T\n\n1. Attendance\ntext # not a heading\n####### seven"


@pytest.mark.parametrize("text", ["#hashtag", "#", "  # indented", "a #tag b", "#1 priority", "####### x"])
def test_md_strip_leaves_non_headings_alone(text: str) -> None:
    from pipeline.extract import strip_md_markers
    assert strip_md_markers(text) == text


def test_md_strip_handles_crlf_tab_and_empty_heading() -> None:
    from pipeline.extract import strip_md_markers
    assert strip_md_markers("## A\r\nb\r\n###\tC") == "A\r\nb\r\nC"
    assert strip_md_markers("# \nx") == "\nx"
    assert strip_md_markers("") == ""
