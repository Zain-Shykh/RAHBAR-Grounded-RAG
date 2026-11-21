"""The four checks (R3-A1-2) as pure functions. Each returns (passed, reason); reasons are shown in the report."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Callable, Sequence

from ..manifest import Entry

Result = tuple[bool, str]

MIN_CHARS = 200            # non-space characters in the whole document (VERIFY_MIN_CHARS)
MIN_ALNUM_RATIO = 0.60     # letters and digits over non-space characters
MAX_REPLACEMENT_RATIO = 0.01
OK = "ok"

# Near-duplicate cosine thresholds per embedding model, from scripts/calibrate_neardup.py (D-113).
# eval/results/neardup-calibration-*.json holds the distributions behind each value.
NEARDUP_THRESHOLD = {"nomic-embed-text": 0.97, "hashing-bow-768": 0.85}
_TERMINAL = tuple('.!?)"\'”’:;')


def normalise(text: str) -> str:
    return " ".join(text.lower().split())


def text_sha256(text: str) -> str:
    return hashlib.sha256(normalise(text).encode()).hexdigest()


def check_quality(*, text: str, extract_error: str | None, integrity_error: str | None,
                  pages: int, empty_pages: int = 0) -> Result:
    if integrity_error:
        return False, integrity_error
    if extract_error:
        return False, f"extraction failed: {extract_error}"
    if pages == 0:
        return False, "extraction returned zero pages"
    chars = "".join(text.split())
    if len(chars) < MIN_CHARS:
        return False, f"empty text ({len(chars)} characters, minimum {MIN_CHARS})"
    alnum = sum(c.isalnum() for c in chars) / len(chars)
    if alnum < MIN_ALNUM_RATIO:
        return False, f"garbled: alphanumeric ratio {alnum:.2f} below {MIN_ALNUM_RATIO}"
    repl = chars.count("�") / len(chars)
    if repl > MAX_REPLACEMENT_RATIO:
        return False, f"garbled: replacement characters {repl:.1%}"
    if pages >= 2 and empty_pages * 2 > pages:
        return False, f"extraction empty on {empty_pages} of {pages} pages"
    return True, OK


def truncation_reason(suffix: str, raw_tail: bytes, text: str) -> str | None:
    suffix = suffix.lower()
    if suffix == ".pdf":
        return None if b"%%EOF" in raw_tail[-1024:] else "truncated: no %%EOF at the end of the PDF"
    if suffix in {".html", ".htm"}:
        return None if b"</html>" in raw_tail[-2048:].lower() else "truncated: HTML has no closing </html>"
    stripped = text.rstrip()
    if stripped and not stripped.endswith(_TERMINAL):
        return f"truncated: text ends mid-sentence ({stripped[-20:]!r})"
    return None


def check_completeness(entry: Entry, *, pages: int, truncated: str | None) -> Result:
    missing = []
    if not entry.file:
        missing.append("source")
    if not entry.title:
        missing.append("title")
    if not entry.has_version_or_date:
        missing.append("date or doc_version")
    if missing:
        return False, "missing " + ", ".join(missing)
    if truncated:
        return False, truncated
    if pages <= 0:
        return False, "page count is zero"
    if entry.pages is not None and pages < entry.pages:
        return False, f"pages {pages} < declared {entry.pages}"
    return True, OK


def _nums(version: str | None) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", version or ""))


def newer_than(a_date: str | None, a_ver: str | None, b_date: str | None, b_ver: str | None) -> bool:
    """True when version b is strictly newer than version a: by date when both have one, else by version."""
    if a_date and b_date:
        return b_date > a_date
    if _nums(a_ver) and _nums(b_ver):
        return _nums(b_ver) > _nums(a_ver)
    return False


def check_recency(entry: Entry, others: Sequence[dict]) -> tuple[Result, str | None]:
    """`others`: dicts with source, family, doc_version, date for every other document known.
    Returns ((passed, reason), source of the newer version or None)."""
    for o in sorted(others, key=lambda d: d["source"]):
        if o["family"] == entry.family and newer_than(entry.date, entry.doc_version, o.get("date"), o.get("doc_version")):
            return (False, f"superseded by {o['source']} ({o.get('doc_version') or o.get('date')} > "
                           f"{entry.doc_version or entry.date})"), o["source"]
    return (True, OK), None


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b, strict=True)) / (na * nb) if na and nb else 0.0


def check_uniqueness(entry: Entry, *, file_sha: str, text_sha: str | None, signature: Sequence[float] | None,
                     originals: Sequence[dict], threshold: float) -> Result:
    """`originals`: dicts with source, family, doc_version, sha256, text_sha256, signature of documents that win."""
    for o in originals:
        if o["source"] == entry.file:
            continue
        if o.get("sha256") == file_sha or (text_sha and o.get("text_sha256") == text_sha):
            return False, f"exact duplicate of {o['source']}"
    if signature:
        for o in originals:
            if o["source"] == entry.file or not o.get("signature"):
                continue
            same_family_other_version = o["family"] == entry.family and o.get("doc_version") != entry.doc_version
            if same_family_other_version:
                continue
            c = cosine(signature, o["signature"])
            if c >= threshold:
                return False, f"near duplicate of {o['source']} (cosine {c:.3f} >= {threshold})"
    return True, OK


def signature(text: str, embed: Callable[[list[str]], list[list[float]]], words: int = 300) -> list[float]:
    """Mean of up to three window embeddings (head, middle, tail), normalised (AD-34)."""
    w = text.split()
    if len(w) <= words:
        windows = [w]
    else:
        mid = max(0, len(w) // 2 - words // 2)
        windows = [w[:words], w[mid:mid + words], w[-words:]]
    vecs = embed(["search_document: " + " ".join(x) for x in windows])
    mean = [sum(col) / len(vecs) for col in zip(*vecs, strict=True)]
    n = math.sqrt(sum(x * x for x in mean)) or 1.0
    return [x / n for x in mean]
