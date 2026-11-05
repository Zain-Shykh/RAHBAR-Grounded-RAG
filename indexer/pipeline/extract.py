"""Stage 1: Extract. PDF (or HTML, or Markdown) to text, page by page (architecture 5.4.2)."""

from __future__ import annotations

import logging
import re
import time
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

import pdfplumber

from .models import Document, Page
from .run import log

OCR_MIN_CHARS = 30
# File name -> x of the column gutters (D-044). The Prospectus is three columns and
# pdfplumber would read it line by line across them. Measured gutters: x 216-224, 393-401.
COLUMN_SPLITS: dict[str, tuple[float, ...]] = {
    "prospectus-2026-academic-rules-and-regulations.pdf": (220.0, 397.0),
    # The two Handbooks are two-page spreads on one clipped MediaBox: the left page ends
    # at x 377, the right page starts at x 445 and runs past the page width (D-052).
    "student-handbook-jun-2026.pdf": (404.0,),
    "academic-rules-handbook-jun-2026.pdf": (400.0,),
}
_CLAUSE = re.compile(r"^\d+(\.\d+)*[.)]?\s+\S")


def needs_ocr(text: str) -> bool:
    """A page with fewer than 30 non-space characters has no usable text layer."""
    return len("".join(text.split())) < OCR_MIN_CHARS


def strip_front_matter(text: str) -> str:
    """Drop a leading `---` ... `---` block; headings stay."""
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1:]).lstrip("\n")
    return text


def strip_md_markers(text: str) -> str:
    """Drop the leading `#` marks of Markdown headings so `## 1. Attendance` reads as the heading
    `1. Attendance` that the chunker's numbered rule recognises (phase 12: CI fixture recall was 0)."""
    return re.sub(r"(?m)^#{1,6}[ \t]+", "", text)


def _key(line: str) -> str:
    return " ".join(re.sub(r"\d+", "", line).split())


def remove_repeating_lines(pages: list[str]) -> list[str]:
    """Remove a line that sits in the top or bottom three lines of at least half the pages.

    Digits are masked so "Title 12" and "Title 13" match. Numbered clause lines are never
    removed. Only edge lines are removed, never page body.
    """
    nonempty = sum(bool(p.strip()) for p in pages)
    if len(pages) < 4 or not nonempty:
        return pages
    edges: list[set[int]] = []
    counts: Counter[str] = Counter()
    split = [p.split("\n") for p in pages]
    for lines in split:
        idx = [i for i, ln in enumerate(lines) if ln.strip()]
        edge = {i for i in idx[:3] + idx[-3:] if not _CLAUSE.match(lines[i].strip())}
        edges.append(edge)
        counts.update({_key(lines[i]) for i in edge})
    repeating = {k for k, n in counts.items() if k and n * 2 >= nonempty}
    return ["\n".join(ln for i, ln in enumerate(lines)
                      if not (i in edge and _key(ln) in repeating))
            for lines, edge in zip(split, edges, strict=True)]


_SKIP_TAGS = {"script", "style", "noscript", "header", "nav", "footer", "form"}
_VOID = {"br", "img", "input", "meta", "link", "hr", "area", "base", "col", "source", "wbr"}
_HEADINGS = {"h1", "h2", "h3", "h4"}
_BLOCKS = {"p", "li", "div", "section", "ul", "ol", "caption", "table", "tr", *_HEADINGS}


class _HtmlText(HTMLParser):
    """Main content to lines. Table row -> one line, cells joined with ' | '."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self.buf: list[str] = []
        self.cell: list[str] | None = None
        self.row: list[str] = []
        self.skip_tag = ""
        self.skip_depth = 0
        self.mark: int | None = None  # index in lines where div.main-content opened

    def _flush(self, after_blank: bool = True) -> None:
        text = " ".join("".join(self.buf).split())
        self.buf = []
        if text:
            self.lines.append(text)
            if after_blank:
                self.lines.append("")

    def _end_cell(self) -> None:
        if self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None

    def _end_row(self) -> None:
        self._end_cell()
        if any(self.row):
            self.lines.append(" | ".join(self.row))
        self.row = []

    def _blank(self) -> None:
        if self.lines and self.lines[-1] != "":
            self.lines.append("")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        cls = dict(attrs).get("class") or ""
        if self.skip_tag:
            self.skip_depth += tag == self.skip_tag
            return
        if tag in _SKIP_TAGS or (tag in {"ol", "ul"} and "breadcrumb" in cls):
            self.skip_tag, self.skip_depth = tag, 1
            return
        if tag == "div" and "main-content" in cls.split() and self.mark is None:
            self.mark = len(self.lines)
        if tag in {"td", "th"}:
            self._end_cell()  # tolerate an unclosed previous cell
            self.cell = []
        elif tag == "br":
            (self.cell if self.cell is not None else self.buf).append(" ")
        elif tag in _BLOCKS and self.cell is None:
            self._flush()
            if tag in _HEADINGS:
                self._blank()
        if tag == "tr":
            self._end_row()

    def handle_endtag(self, tag: str) -> None:
        if self.skip_tag:
            if tag == self.skip_tag:
                self.skip_depth -= 1
                if self.skip_depth == 0:
                    self.skip_tag = ""
            return
        if tag in {"td", "th"}:
            self._end_cell()
        elif tag == "tr":
            self._end_row()
        elif tag == "table":
            self._end_row()
            self._blank()
        elif tag in _BLOCKS and self.cell is None:
            self._flush(after_blank=tag not in _HEADINGS and tag != "caption")

    def handle_data(self, data: str) -> None:
        if self.skip_tag:
            return
        (self.cell if self.cell is not None else self.buf).append(data)


def html_to_text(html: str) -> str:
    """Main content as text: headings and paragraphs as lines, one line per table row."""
    parser = _HtmlText()
    parser.feed(html)
    parser.close()
    parser._end_row()
    parser._flush()
    lines = parser.lines[parser.mark or 0:]
    return "\n".join(lines).strip()


def _ocr_page(path: str, n: int) -> str:
    """OCR one page (200 dpi). Imports here so unit tests and CI-mode need no system packages."""
    import pytesseract
    from pdf2image import convert_from_path

    img = convert_from_path(path, dpi=200, first_page=n, last_page=n)[0]
    try:
        return str(pytesseract.image_to_string(img, lang="eng"))
    finally:
        img.close()


def _page_text(page: pdfplumber.page.Page, splits: tuple[float, ...]) -> str:
    if not splits:
        return page.extract_text() or ""
    right = max([float(page.width), *(float(w["x1"]) + 1 for w in page.extract_words())])
    edges = [0.0, *splits, right]  # content may run past the MediaBox (spread pages)
    cols = [page.crop((a, 0, b, page.height), strict=False).extract_text() or ""
            for a, b in zip(edges, edges[1:], strict=False)]
    return "\n\n".join(c for c in cols if c)


def _extract_pdf(path: str, name: str) -> list[Page]:
    logging.getLogger("pdfminer").setLevel(logging.ERROR)  # one "CropBox missing" per page
    texts: list[str] = []
    ocr_pages: set[int] = set()
    splits = COLUMN_SPLITS.get(name, ())
    with pdfplumber.open(path) as pdf:
        for n, page in enumerate(pdf.pages, 1):
            text = _page_text(page, splits)
            page.flush_cache()
            if needs_ocr(text):
                ocr_pages.add(n)
                try:
                    text = _ocr_page(path, n)
                except Exception as exc:  # one bad page must not fail the Job
                    log("ocr failed", source=name, page=n, error=repr(exc))
                    text = ""
            texts.append(text)
    texts = remove_repeating_lines(texts)
    return [Page(name, n, t, ocr=n in ocr_pages) for n, t in enumerate(texts, 1)]


def extract(path: str, doc_version: str, superseded: bool) -> Document:
    """Return the document's text page by page; pages without a text layer are OCR'd."""
    name = Path(path).name
    started = time.perf_counter()
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        pages = _extract_pdf(path, name)
    elif suffix in {".html", ".htm"}:
        pages = [Page(name, 1, html_to_text(Path(path).read_text(encoding="utf-8", errors="replace")))]
    elif suffix in {".md", ".txt"}:
        text = Path(path).read_text(encoding="utf-8")
        pages = [Page(name, 1, strip_md_markers(strip_front_matter(text)) if suffix == ".md" else text)]
    else:
        raise ValueError(f"unsupported file type: {name}")
    log("extracted", source=name, pages=len(pages), ocr_pages=sum(p.ocr for p in pages),
        seconds=round(time.perf_counter() - started, 1))
    return Document(name, doc_version, superseded, pages)
