"""Stage 2: Clean. Remove artefacts without destroying structure (architecture 5.4.2).

Deliberately NOT stripped: clause numbers and heading numbering, even when OCR
mangled them (`92.` for `9.2`): dropping them would hide the loss.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import replace

from .models import Document

_INVISIBLE = dict.fromkeys(map(ord, "\x0c​‌‍⁠﻿­"))
_HSPACE = re.compile(r"[ \t]+")
_HYPHEN = re.compile(r"(\w)-\n(?=[a-z])")
_PAGE_NO = re.compile(r"^(?:page\s+)?\d{1,3}(?:\s+of\s+\d{1,3})?$|^[-–—]\s*\d{1,3}\s*[-–—]$", re.I)
_BLANKS = re.compile(r"\n{3,}")


def repair_letter_spacing(line: str) -> str:
    """Join runs of 5+ single-character tokens ("7 5 %" -> "75%") on a mostly letter-spaced line.

    ponytail: word spaces inside a repaired run are lost; a segmenter would restore them.
    """
    tokens = line.split(" ")
    if len(tokens) < 5 or sum(len(t) == 1 for t in tokens) < 0.7 * len(tokens):
        return line
    out: list[str] = []
    run: list[str] = []
    for t in [*tokens, "  "]:  # sentinel flushes the last run
        if len(t) == 1:
            run.append(t)
            continue
        if len(run) >= 5:
            out.append("".join(run))
        else:
            out.extend(run)
        run = []
        out.append(t)
    return " ".join(out[:-1])


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_INVISIBLE)
    text = "".join(" " if unicodedata.category(c) == "Zs" else c for c in text)
    lines = [repair_letter_spacing(_HSPACE.sub(" ", ln).strip()) for ln in text.split("\n")]
    text = _HYPHEN.sub(r"\1", "\n".join(lines))
    text = "\n".join(ln for ln in text.split("\n") if not _PAGE_NO.match(ln))
    return _BLANKS.sub("\n\n", text).strip()


def clean(doc: Document) -> Document:
    """Return a cleaned copy; headings and section boundaries are kept."""
    return replace(doc, pages=[replace(p, text=clean_text(p.text)) for p in doc.pages])
