"""Stage 1: Extract. PDF (or HTML, or Markdown) to text, page by page (architecture 5.4.2)."""

from __future__ import annotations

import logging
import re
import time
from collections import Counter
from pathlib import Path

import pdfplumber

from .models import Document, Page
from .run import log

OCR_MIN_CHARS = 30
# File name -> x of the column gutters (D-044). The Prospectus is three columns and
# pdfplumber would read it line by line across them. Measured gutters: x 216-224, 393-401.
COLUMN_SPLITS: dict[str, tuple[float, ...]] = {
    "prospectus-2026-academic-rules-and-regulations.pdf": (220.0, 397.0),
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


def _key(line: str) -> str:
    return " ".join(re.sub(r"\d+", "#", line).split())


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
    edges = [0.0, *splits, float(page.width)]
    cols = [page.crop((a, 0, b, page.height)).extract_text() or ""
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
    elif suffix in {".md", ".txt"}:
        text = Path(path).read_text(encoding="utf-8")
        pages = [Page(name, 1, strip_front_matter(text) if suffix == ".md" else text)]
    else:
        raise ValueError(f"unsupported file type: {name}")
    log("extracted", source=name, pages=len(pages), ocr_pages=sum(p.ocr for p in pages),
        seconds=round(time.perf_counter() - started, 1))
    return Document(name, doc_version, superseded, pages)
