"""Version intent, by rules (architecture 5.6.2, AD-11). Pure: no I/O.

A year in the question picks the matching document versions; an "older version" phrase
searches every version; otherwise only current (not superseded) documents are searched.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha1

_YEAR = re.compile(r"\b(20\d\d(?:-\d\d)?)\b")
_OLDER = re.compile(
    r"\b(?:old|older|previous|former|earlier|prior|superseded|repealed|before|used\s+to)\b", re.I
)


@dataclass(frozen=True)
class Scope:
    where: dict[str, object] | None   # Chroma `where`; None means no filter
    key: str                          # "current", "all", or the matched versions joined by "+"

    @property
    def tag(self) -> str:
        """The cache scope tag (AD-05): a 2023-rules question never hits a 2026 answer."""
        return sha1(self.key.encode()).hexdigest()[:12]


def scope(question: str, doc_versions: Iterable[str]) -> Scope:
    versions = sorted(set(doc_versions))
    matched = sorted({v for y in _YEAR.findall(question) for v in versions if v.startswith(y)})
    if matched:
        return Scope({"doc_version": {"$in": matched}}, "+".join(matched))
    if _OLDER.search(question):
        return Scope(None, "all")
    return Scope({"superseded": False}, "current")
