"""Stage 1: Extract. PDF (or HTML, or Markdown) to text, page by page (architecture 5.4.2)."""

from __future__ import annotations

import re
from collections import Counter

from .models import Document

OCR_MIN_CHARS = 30
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


def extract(path: str, doc_version: str, superseded: bool) -> Document:
    """Return the document's text page by page."""
    raise NotImplementedError("extract: pdf and html arrive in later steps")
