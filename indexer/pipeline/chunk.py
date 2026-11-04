"""Stage 3: Chunk. Structure-aware, with overlap (architecture 5.4.2, phase 6 spec, DEV-003).

Headings first, then paragraphs, then sentences, packed to `size` words. The unit is words
(AD-10). Overlap is the tail of the previous chunk of the same section.
"""

from __future__ import annotations

import re
from pathlib import Path

from .models import Chunk, Document

_NUM = re.compile(r"^\d{1,2}(?:\.\d+)*\.?\s+(\S)")
_ROMAN = re.compile(r"^[IVXLC]{1,6}\s*[-–—.]\s*[A-Z][A-Z &/,'-]{3,}$")
_LETTER = re.compile(r"^[A-Z][.)]\s+[A-Z]")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
SECTION_MAX = 80  # characters; D-049
_Unit = tuple[str, int, bool]  # text, page, is_table_row


def _numeric(token: str) -> bool:
    return token.replace(",", "").replace(".", "").isdigit()


def _heading(line: str, prev_blank: bool, has_body: bool) -> str | None:
    """The section name if `line` is a heading, else None. Rules: numbered clause, roman,
    lettered, all caps, and (DEV-003) an isolated short line: blank above, text below."""
    if not line or " | " in line or len(line) > 200:
        return None
    n = len(line.split())
    letters = sum(c.isalpha() for c in line)
    num = _NUM.match(line)
    if num and (num.group(1).isupper() or num.group(1) == "("):
        ok = True
    elif _ROMAN.match(line):
        ok = True
    elif _LETTER.match(line):
        ok = n <= 10 and not line.endswith(".")
    elif line == line.upper():
        ok = letters >= 4 and n <= 10 and not line.endswith(".")
    else:
        ok = (prev_blank and has_body and letters >= 4 and n <= 10 and line[0].isupper()
              and line[-1] not in ".:;,!?" and sum(map(_numeric, line.split())) * 2 < n)
    if not ok:
        return None
    name = " ".join(line.split())
    if len(name) > SECTION_MAX:  # cut on a word boundary
        cut = name[:SECTION_MAX]
        name = cut if name[SECTION_MAX] == " " or " " not in cut else cut.rsplit(" ", 1)[0]
    return name


def _title_like(name: str) -> bool:
    """A short heading with no final period is a title: a heading right below it joins it."""
    return len(name.split()) <= 10 and not name.endswith(".")


def _split(text: str, page: int, size: int) -> list[_Unit]:
    """One unit for a paragraph that fits; else sentences; a sentence over `size`, word pieces."""
    if len(text.split()) <= size:
        return [(text, page, False)]
    units: list[_Unit] = []
    for sentence in _SENTENCE.split(text):
        w = sentence.split()
        for i in range(0, len(w), size):
            units.append((" ".join(w[i:i + size]) if len(w) > size else sentence, page, False))
    return units


def _pack(units: list[_Unit], size: int, overlap: int) -> list[tuple[str, int]]:
    """Greedy packing of one section's units. Returns (text, page of first new unit)."""
    out: list[tuple[str, int]] = []
    pre: list[str] = []
    body: list[str] = []
    count = page = 0
    row = False

    def text() -> str:
        return (" ".join(pre) + "\n" if pre else "") + "\n".join(body)

    for unit, pg, is_row in units:
        w = len(unit.split())
        if body and count + w > size:
            out.append((text(), page))
            keep = 0 if row else max(0, min(overlap, size - w))  # no overlap after a table row
            pre = text().split()[-keep:] if keep else []
            body, count = [], len(pre)
        if not body:
            page = pg
        body.append(unit)
        count += w
        row = is_row
    if body:
        out.append((text(), page))
    return out


def chunk(doc: Document, size: int, overlap: int) -> list[Chunk]:
    """Split on headings, then paragraphs, then sentences, keeping each chunk within `size`
    words (only a single table row may exceed it), with `overlap` words shared between
    neighbours of the same section. Every chunk keeps the heading it sits under, its page,
    doc_version and superseded. Ids: `<stem>-p<page:03d>-c<seq:03d>`, seq from 1 (D-051)."""
    if size < 1 or overlap < 0 or overlap >= size:
        raise ValueError(f"need size >= 1 and 0 <= overlap < size, got {size}, {overlap}")
    stem = Path(doc.source).stem
    sections: list[tuple[str, list[_Unit]]] = []
    name, units = stem, []
    para: list[str] = []
    para_page = 1
    title_only = False  # the section so far is one title with no body

    def end_para() -> None:
        nonlocal para
        if para:
            units.extend(_split("\n".join(para), para_page, size))
            para = []

    for page in doc.pages:
        lines = [ln.strip() for ln in page.text.split("\n")]
        for i, line in enumerate(lines):
            if not line:
                end_para()
                continue
            h = _heading(line, i == 0 or not lines[i - 1], i + 1 < len(lines) and bool(lines[i + 1]))
            if h and not title_only:
                end_para()
                sections.append((name, units))
                name, units = h, []
                para, para_page = [line], page.page
                title_only = _title_like(h)
                continue
            if " | " in line:
                end_para()
                units.append((line, page.page, True))
            else:
                if not para:
                    para_page = page.page
                para.append(line)
            title_only = title_only and bool(h)
        end_para()
    sections.append((name, units))

    chunks: list[Chunk] = []
    for section, section_units in sections:
        for text, pg in _pack(section_units, size, overlap):
            cid = f"{stem}-p{pg:03d}-c{len(chunks) + 1:03d}"
            chunks.append(Chunk(cid, text, doc.source, section, pg, doc.doc_version, doc.superseded))
    return chunks
