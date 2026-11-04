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
