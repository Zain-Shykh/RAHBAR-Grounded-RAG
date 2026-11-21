"""Build candidates, run the four checks, decide an action per document (architecture-a3 5.3).

`Candidate` holds everything one document needs; `decide()` is pure given candidates and the registry
view, so it is tested without files. `build_candidate()` touches the disk and the extractor.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ..manifest import Entry
from ..models import Document
from . import checks as C

CHECKS = ("quality", "completeness", "recency", "uniqueness")


@dataclass
class Candidate:
    entry: Entry
    path: Path
    file_sha: str = ""
    integrity_error: str | None = None
    extract_error: str | None = None
    doc: Document | None = None
    text: str = ""
    pages: int = 0
    empty_pages: int = 0
    truncated: str | None = None
    text_sha: str | None = None
    signature: list[float] | None = None


@dataclass
class Verdict:
    source: str
    action: str                       # index | quarantine | supersede | supersede_registry
    checks: dict[str, dict] = field(default_factory=dict)
    note: str = ""

    @property
    def failed(self) -> list[str]:
        return [k for k, v in self.checks.items() if not v["pass"]]

    def reasons(self) -> list[str]:
        return [f"{k}: {v['reason']}" for k, v in self.checks.items() if not v["pass"]]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(1 << 20):
            h.update(block)
    return h.hexdigest()


def build_candidate(entry: Entry, corpus_dir: str, *, extract: Callable[..., Document],
                    embed_texts: Callable[[list[str]], list[list[float]]] | None) -> Candidate:
    path = Path(corpus_dir) / entry.file
    c = Candidate(entry=entry, path=path)
    if not path.is_file():
        c.integrity_error = f"missing file: {entry.file}"
        return c
    c.file_sha = _sha256(path)
    if entry.sha256 and entry.sha256 != c.file_sha:
        c.integrity_error = f"integrity: sha256 mismatch (manifest {entry.sha256[:12]}, file {c.file_sha[:12]})"
    raw_tail = path.read_bytes()[-4096:]
    try:
        c.doc = extract(str(path), entry.doc_version or "unknown", entry.superseded)
        c.pages = len(c.doc.pages)
        c.empty_pages = sum(1 for p in c.doc.pages if not "".join(p.text.split()))
        c.text = "\n".join(p.text for p in c.doc.pages)
    except Exception as exc:  # a bad file is a verdict, not a crash
        c.extract_error = f"{type(exc).__name__}"
    c.truncated = C.truncation_reason(path.suffix, raw_tail, c.text)
    if c.text.strip() and c.integrity_error is None and c.extract_error is None and embed_texts:
        c.text_sha = C.text_sha256(c.text)
        c.signature = C.signature(c.text, embed_texts)
    elif c.text.strip():
        c.text_sha = C.text_sha256(c.text)
    return c


def _row(ok: bool, reason: str) -> dict:
    return {"pass": ok, "reason": reason}


def decide(cands: list[Candidate], registry: dict[str, dict], *, threshold: float) -> list[Verdict]:
    """Verdicts for every candidate, plus `supersede_registry` verdicts for registry documents that a
    candidate supersedes. `registry` maps source -> {sha256, text_sha256, signature, family, doc_version, date}."""
    verdicts: dict[str, Verdict] = {}
    originals: list[dict] = [{"source": s, **{k: r.get(k) for k in ("family", "doc_version", "date", "sha256",
                              "text_sha256", "signature")}} for s, r in registry.items()]
    known = [{"source": o["source"], "family": o["family"], "doc_version": o["doc_version"], "date": o["date"]}
             for o in originals]
    known += [{"source": c.entry.file, "family": c.entry.family, "doc_version": c.entry.doc_version,
               "date": c.entry.date} for c in cands]
    superseded_registry: dict[str, str] = {}
    for c in sorted(cands, key=lambda x: x.entry.file):
        e = c.entry
        q = C.check_quality(text=c.text, extract_error=c.extract_error, integrity_error=c.integrity_error,
                            pages=c.pages, empty_pages=c.empty_pages)
        comp = C.check_completeness(e, pages=c.pages, truncated=c.truncated)
        (rec_ok, rec_reason), newer = C.check_recency(e, [k for k in known if k["source"] != e.file])
        if not rec_ok and e.superseded:
            rec_ok, rec_reason = True, f"already marked superseded in the manifest ({rec_reason})"
        uniq = C.check_uniqueness(e, file_sha=c.file_sha, text_sha=c.text_sha, signature=c.signature,
                                  originals=originals, threshold=threshold)
        v = Verdict(e.file, "index", {"quality": _row(*q), "completeness": _row(*comp),
                                      "recency": _row(rec_ok, rec_reason), "uniqueness": _row(*uniq)})
        if not (q[0] and comp[0] and uniq[0]):
            v.action = "quarantine"
        else:
            if not rec_ok:
                v.action = "supersede"
            originals.append({"source": e.file, "family": e.family, "doc_version": e.doc_version, "date": e.date,
                              "sha256": c.file_sha, "text_sha256": c.text_sha, "signature": c.signature})
            for r in registry:           # does this passing document supersede a registry document?
                rr = registry[r]
                if rr["family"] == e.family and C.newer_than(rr.get("date"), rr.get("doc_version"), e.date, e.doc_version) \
                        and not registry[r].get("superseded") and not registry[r].get("pinned"):
                    superseded_registry[r] = e.file
        verdicts[e.file] = v
    out = [verdicts[k] for k in sorted(verdicts)]
    for src, newer_src in sorted(superseded_registry.items()):
        rr = registry[src]
        out.append(Verdict(src, "supersede_registry", {
            "quality": _row(True, "indexed earlier"), "completeness": _row(True, "indexed earlier"),
            "recency": _row(False, f"superseded by {newer_src} ({rr.get('doc_version') or rr.get('date')} older)"),
            "uniqueness": _row(True, "indexed earlier")}))
    return out
